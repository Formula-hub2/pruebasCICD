import pyotp
from locust import HttpUser, TaskSet, task

from core.environment.host import get_host_for_locust_testing
from core.locust.common import fake, get_csrf_token


class SignupBehavior(TaskSet):
    def on_start(self):
        self.signup()

    @task
    def signup(self):
        response = self.client.get("/signup")
        csrf_token = get_csrf_token(response)

        response = self.client.post(
            "/signup", data={"email": fake.email(), "password": fake.password(), "csrf_token": csrf_token}
        )
        if response.status_code != 200:
            print(f"Signup failed: {response.status_code}")


class LoginBehavior(TaskSet):
    def on_start(self):
        self.ensure_logged_out()
        self.login()

    @task
    def ensure_logged_out(self):
        response = self.client.get("/logout")
        if response.status_code != 200:
            print(f"Logout failed or no active session: {response.status_code}")

    @task
    def login(self):
        response = self.client.get("/login")
        if response.status_code != 200 or "Login" not in response.text:
            print("Already logged in or unexpected response, redirecting to logout")
            self.ensure_logged_out()
            response = self.client.get("/login")

        csrf_token = get_csrf_token(response)

        response = self.client.post(
            "/login", data={"email": "user1@example.com", "password": "1234", "csrf_token": csrf_token}
        )
        if response.status_code != 200:
            print(f"Login failed: {response.status_code}")


class AuthUser(HttpUser):
    tasks = [SignupBehavior, LoginBehavior]
    min_wait = 5000
    max_wait = 9000
    host = get_host_for_locust_testing()


class TwoFactorLoginBehavior(TaskSet):
    def on_start(self):
        """Al iniciar, aseguramos sesión limpia e intentamos el login completo"""
        self.ensure_logged_out()
        self.login_with_2fa()

    def ensure_logged_out(self):
        self.client.get("/logout")

    @task
    def login_with_2fa(self):
        # Limpieza agresiva de cookies para forzar que nos pida 2FA
        self.client.cookies.clear()

        # 2. GET LOGIN
        response = self.client.get("/login")
        try:
            csrf_token_login = get_csrf_token(response)
        except ValueError:
            return  # Si falla aquí, reiniciamos

        # 3. POST CREDENCIALES
        # Nota: Importante no enviar cookies de device_id si queremos forzar el 2FA
        response = self.client.post(
            "/login", data={"email": "user1@example.com", "password": "1234", "csrf_token": csrf_token_login}
        )

        # --- AQUÍ ESTÁ EL ARREGLO ---

        # Caso A: Nos mandó al Index (Se saltó el 2FA o login normal)
        if "/verify_2fa" not in response.url:
            if response.status_code == 200:
                print(
                    f"⚠️ 2FA OMITIDO: El servidor nos mandó directo a {response.url}. "
                    "(Posible cookie device_id residual)"
                )
            else:
                print(f"❌ Login fallido. Status: {response.status_code}")
            return  # Terminamos esta tarea aquí, no intentamos buscar tokens que no existen

        # Caso B: Estamos correctamente en la pantalla de 2FA
        try:
            # Ahora sí es seguro buscar el token, porque sabemos que estamos en la página correcta
            csrf_token_2fa = get_csrf_token(response)
        except ValueError:
            print("❌ Estamos en /verify_2fa pero no veo el input hidden csrf_token.")
            return

        # Generar código y enviar
        # COPIAR SECRET DE LA DB EN CASO DE REINICIARLA
        secret = "VHZHTPR5ZSXR564A2XTZ56JSLUA4XNYK"
        totp = pyotp.TOTP(secret).now()

        response_final = self.client.post("/verify_2fa", data={"token": totp, "csrf_token": csrf_token_2fa})

        if response_final.status_code == 200 and "/verify_2fa" not in response_final.url:
            print("✅ 2FA Completado Exitosamente")
        else:
            print("❌ Fallo al enviar el código TOTP.")


class AuthUser2FA(HttpUser):
    # Ejecutamos solo el comportamiento de 2FA
    tasks = [TwoFactorLoginBehavior]
    min_wait = 5000
    max_wait = 9000
    host = get_host_for_locust_testing()
