"""Consultas parametrizadas y autorización por propietario para cada recurso."""
from datetime import date
from uuid import uuid4

from psycopg.types.json import Jsonb

from apps.api.app.db.postgres import Database


class FarmerRepository:
    def __init__(self, database: Database):
        self.database = database

    def consume_attempt(self, bucket, window_seconds, maximum):
        with self.database.connect() as conn:
            conn.execute("DELETE FROM auth_rate_limits WHERE window_started < now()-interval '2 days'")
            row = conn.execute("""INSERT INTO auth_rate_limits(bucket,attempts) VALUES(%s,1)
                ON CONFLICT(bucket) DO UPDATE SET
                  attempts=CASE WHEN auth_rate_limits.window_started < now()-(%s*interval '1 second') THEN 1 ELSE auth_rate_limits.attempts+1 END,
                  window_started=CASE WHEN auth_rate_limits.window_started < now()-(%s*interval '1 second') THEN now() ELSE auth_rate_limits.window_started END
                RETURNING attempts""", (bucket, window_seconds, window_seconds)).fetchone()
            return row['attempts'] <= maximum

    def user_by_email(self, email):
        with self.database.connect() as conn:
            return conn.execute('SELECT * FROM farmer_users WHERE email=%s', (email,)).fetchone()

    def create_user(self, email, name, password_hash):
        with self.database.connect() as conn:
            return conn.execute("""INSERT INTO farmer_users(user_id,email,display_name,password_hash)
                VALUES(%s,%s,%s,%s) ON CONFLICT(email) DO NOTHING RETURNING user_id,email,display_name,created_at""",
                (uuid4(), email, name, password_hash)).fetchone()

    def rehash(self, user_id, value):
        with self.database.connect() as conn:
            conn.execute('UPDATE farmer_users SET password_hash=%s WHERE user_id=%s', (value, user_id))

    def create_session(self, user_id, token_hash, expires_at):
        with self.database.connect() as conn:
            conn.execute('DELETE FROM farmer_sessions WHERE expires_at<=now()')
            conn.execute('INSERT INTO farmer_sessions(token_hash,user_id,expires_at) VALUES(%s,%s,%s)',
                         (token_hash, user_id, expires_at))

    def session(self, token_hash):
        with self.database.connect() as conn:
            return conn.execute("""SELECT u.user_id,u.email,u.display_name,u.created_at,s.expires_at
                FROM farmer_sessions s JOIN farmer_users u USING(user_id)
                WHERE s.token_hash=%s AND s.expires_at>now()""", (token_hash,)).fetchone()

    def revoke_session(self, token_hash):
        with self.database.connect() as conn:
            conn.execute('DELETE FROM farmer_sessions WHERE token_hash=%s', (token_hash,))

    @staticmethod
    def _farm(row):
        if row is None:
            return None
        return {**row['body'], **{key:row[key] for key in ('farm_id','revision','created_at','updated_at')}}

    def farms(self, owner):
        with self.database.connect() as conn:
            return [self._farm(row) for row in conn.execute('SELECT * FROM farms WHERE owner_id=%s ORDER BY created_at', (owner,)).fetchall()]

    def farm(self, owner, farm_id):
        with self.database.connect() as conn:
            return self._farm(conn.execute('SELECT * FROM farms WHERE owner_id=%s AND farm_id=%s', (owner, farm_id)).fetchone())

    def create_farm(self, owner, body):
        with self.database.connect() as conn:
            # Serializar creación por cuenta para aplicar la cuota también con peticiones simultáneas.
            conn.execute('SELECT user_id FROM farmer_users WHERE user_id=%s FOR UPDATE', (owner,))
            count = conn.execute('SELECT count(*) AS n FROM farms WHERE owner_id=%s', (owner,)).fetchone()['n']
            if count >= 20:
                return None
            return self._farm(conn.execute('INSERT INTO farms(farm_id,owner_id,body) VALUES(%s,%s,%s) RETURNING *',
                                          (uuid4(), owner, Jsonb(body))).fetchone())

    def update_farm(self, owner, farm_id, body, expected_revision):
        with self.database.connect() as conn:
            return self._farm(conn.execute("""UPDATE farms SET body=%s,revision=revision+1,updated_at=now()
                WHERE owner_id=%s AND farm_id=%s AND revision=%s RETURNING *""",
                (Jsonb(body), owner, farm_id, expected_revision)).fetchone())

    def datasets(self, owner, farm_id):
        with self.database.connect() as conn:
            return conn.execute("""SELECT d.* FROM farm_datasets d JOIN farms f USING(farm_id)
                WHERE f.owner_id=%s AND f.farm_id=%s ORDER BY d.created_at DESC""", (owner, farm_id)).fetchall()

    def dataset(self, owner, farm_id, dataset_id):
        with self.database.connect() as conn:
            return conn.execute("""SELECT d.* FROM farm_datasets d JOIN farms f USING(farm_id)
                WHERE f.owner_id=%s AND f.farm_id=%s AND d.dataset_id=%s""", (owner, farm_id, dataset_id)).fetchone()

    def duplicate(self, owner, farm_id, digest):
        with self.database.connect() as conn:
            return conn.execute("""SELECT d.* FROM farm_datasets d JOIN farms f USING(farm_id)
                WHERE f.owner_id=%s AND f.farm_id=%s AND d.sha256=%s""", (owner, farm_id, digest)).fetchone()

    def store_dataset(self, owner, farm_id, dataset, rows):
        with self.database.connect() as conn:
            farm = conn.execute('SELECT farm_id FROM farms WHERE farm_id=%s AND owner_id=%s FOR UPDATE', (farm_id, owner)).fetchone()
            if farm is None:
                raise PermissionError('Finca no encontrada')
            count = conn.execute('SELECT count(*) AS n FROM farm_datasets WHERE farm_id=%s', (farm_id,)).fetchone()['n']
            if count >= 20:
                raise ValueError('Cada finca admite hasta 20 datasets; elimina uno antes de cargar otro.')
            result = conn.execute("""INSERT INTO farm_datasets(dataset_id,farm_id,original_filename,storage_key,
                sha256,row_count,first_date,last_date,variables) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (dataset['dataset_id'], farm_id, dataset['original_filename'], dataset['storage_key'], dataset['sha256'],
                 len(rows), min(row['date'] for row in rows), max(row['date'] for row in rows),
                 Jsonb(sorted({row['variable'] for row in rows})))).fetchone()
            with conn.cursor() as cursor:
                cursor.executemany('INSERT INTO farm_observations(dataset_id,observed_date,variable,value,unit,crop) VALUES(%s,%s,%s,%s,%s,%s)',
                                   [(dataset['dataset_id'], row['date'], row['variable'], row['value'], row['unit'], row['crop']) for row in rows])
            return result

    def delete_dataset(self, owner, farm_id, dataset_id):
        with self.database.connect() as conn:
            return conn.execute("""DELETE FROM farm_datasets d USING farms f
                WHERE d.farm_id=f.farm_id AND f.owner_id=%s AND f.farm_id=%s AND d.dataset_id=%s
                RETURNING d.storage_key""", (owner, farm_id, dataset_id)).fetchone()

    def feature_rows(self, owner, farm_id, cutoff: date):
        with self.database.connect() as conn:
            return conn.execute("""SELECT o.dataset_id,o.observed_date AS date,o.variable,o.value,o.unit,o.crop
                FROM farm_observations o JOIN farm_datasets d USING(dataset_id) JOIN farms f USING(farm_id)
                WHERE f.owner_id=%s AND f.farm_id=%s AND o.observed_date<=%s
                ORDER BY o.observed_date,o.variable,o.crop,o.dataset_id""", (owner, farm_id, cutoff)).fetchall()

    def context_snapshot(self, owner, farm_id, cutoff: date):
        with self.database.connect() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            farm = self._farm(conn.execute('SELECT * FROM farms WHERE owner_id=%s AND farm_id=%s', (owner, farm_id)).fetchone())
            if farm is None:
                return None, [], []
            versions = conn.execute('SELECT * FROM farm_datasets WHERE farm_id=%s ORDER BY created_at', (farm_id,)).fetchall()
            observations = conn.execute("""SELECT o.dataset_id,o.observed_date AS date,o.variable,o.value,o.unit,o.crop
                FROM farm_observations o JOIN farm_datasets d USING(dataset_id)
                WHERE d.farm_id=%s AND o.observed_date<=%s
                ORDER BY o.observed_date,o.variable,o.crop,o.dataset_id""", (farm_id, cutoff)).fetchall()
            return farm, observations, versions
