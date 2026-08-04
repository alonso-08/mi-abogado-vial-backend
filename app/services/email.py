import asyncio
import logging
from typing import Any, Dict, Optional

import resend

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmailService:
    """Servicio para envio de emails usando Resend"""

    def __init__(self):
        if not settings.RESEND_API_KEY:
            logger.warning("RESEND_API_KEY no configurada. Los emails no se enviaran.")
            self.enabled = False
        else:
            resend.api_key = settings.RESEND_API_KEY
            self.enabled = True

    def _send_sync(
        self,
        to_email: str,
        subject: str,
        html_content: str,
    ) -> Dict[str, Any]:
        from_address = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"

        response = resend.Emails.send(
            {
                "from": from_address,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
            }
        )

        logger.info(f"Email sent to {to_email}. ID: {response.get('id')}")
        return {"success": True, "email_id": response.get("id")}

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
    ) -> Dict[str, Any]:
        if not self.enabled:
            logger.warning(f"Email disabled. Would send to {to_email}: {subject}")
            return {"success": False, "message": "Email service not configured"}

        try:
            return await asyncio.to_thread(self._send_sync, to_email, subject, html_content)
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return {"success": False, "message": str(e)}

    async def send_verification_email(
        self, to_email: str, full_name: str, verification_token: str
    ) -> Dict[str, Any]:
        verification_url = f"{settings.BACKEND_URL}/api/auth/verify-email/{verification_token}"

        html_content = self._generate_verification_email_html(
            full_name=full_name or to_email,
            verification_url=verification_url,
        )

        return await self.send_email(
            to_email=to_email,
            subject="Verifica tu cuenta - Asistente Legal Vial",
            html_content=html_content,
        )

    def _generate_verification_email_html(self, full_name: str, verification_url: str) -> str:
        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verifica tu cuenta</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
                    color: white;
                    padding: 30px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                }}
                .content {{
                    background: #ffffff;
                    padding: 30px;
                    border: 1px solid #e1e1e1;
                }}
                .button {{
                    display: inline-block;
                    background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
                    color: white !important;
                    text-decoration: none;
                    padding: 15px 30px;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 20px 0;
                }}
                .footer {{
                    background: #f8f9fa;
                    padding: 20px;
                    text-align: center;
                    font-size: 12px;
                    color: #666666;
                    border-radius: 0 0 8px 8px;
                    border: 1px solid #e1e1e1;
                    border-top: none;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">⚖️ Asistente Legal Vial</div>
                <h1>¡Bienvenido!</h1>
            </div>

            <div class="content">
                <h2>Hola {full_name},</h2>

                <p>Gracias por registrarte en <strong>Asistente Legal Vial</strong>. Estamos aqui para ayudarte a conocer tus derechos al momento de un retencion vial.</p>

                <p>Para completar tu registro y acceder a todas las funcionalidades, necesitas verificar tu direccion de email.</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" class="button">
                        Verificar mi cuenta
                    </a>
                </div>

                <p>Una vez verificada tu cuenta, podras:</p>
                <ul>
                    <li>Consultar tus derechos ante el trafico</li>
                    <li>Recibir asesoria legal inmediata</li>
                    <li>Acceder a la legislacion de tu estado</li>
                </ul>

                <p>Si no has creado una cuenta con nosotros, puedes ignorar este email de forma segura.</p>

                <hr style="margin: 30px 0; border: none; border-top: 1px solid #e1e1e1;">

                <p><small>
                    <strong>Nota:</strong> Este enlace de verificacion expirara en 24 horas por seguridad.
                    Si no puedes hacer clic en el boton, copia y pega esta URL en tu navegador:
                </small></p>
                <p><small style="color: #666; word-break: break-all;">{verification_url}</small></p>
            </div>

            <div class="footer">
                <p><strong>Asistente Legal Vial</strong> - Conoce tus derechos</p>
                <p>Este email fue enviado porque creaste una cuenta en nuestra plataforma.</p>
            </div>
        </body>
        </html>
        """


email_service = EmailService()
