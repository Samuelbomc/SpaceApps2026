import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
@Component({
  selector: 'app-password-recovery',
  imports: [RouterLink],
  template: `<section class="section">
    <div class="container">
      <h1>Recuperar contraseña</h1>
      <p>La recuperación de contraseña aún no está disponible.</p>
      <a class="btn btn--primary" routerLink="/acceso">Volver a iniciar sesión</a>
    </div>
  </section>`,
})
export class PasswordRecovery {}
