import { Component, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import { AuthService } from '../../core/auth/auth.service';
@Component({
  selector: 'app-profile',
  imports: [DatePipe],
  template: `<section class="section">
    <div class="container">
      <h1>Mi perfil</h1>
      @if (auth.user(); as user) {
        <dl class="card spec-list">
          <dt>Nombre</dt>
          <dd>{{ user.name }}</dd>
          <dt>Correo</dt>
          <dd>{{ user.email }}</dd>
          <dt>Cuenta creada</dt>
          <dd>{{ auth.session()?.startedAt | date: 'medium' }}</dd>
        </dl>
      }
      <p>La modificación del perfil todavía no está disponible.</p>
    </div>
  </section>`,
})
export class Profile {
  protected readonly auth = inject(AuthService);
}
