"""
Email dispatch service — renders Jinja2 HTML templates and dispatches via Resend API.
Fire-and-forget logic: Email send failures are logged but never fail user API requests.
"""

import logging
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)


def _get_from_address(fallback_dev: bool = False) -> str:
    """Return formatted sender address for Resend."""
    from_email = "onboarding@resend.dev" if fallback_dev else (settings.FROM_EMAIL or "onboarding@resend.dev")
    from_name = settings.FROM_NAME or "Negentrophi"
    return f"{from_name} <{from_email}>"


async def send_otp_email(
    to_email: str,
    otp_code: str,
    purpose: str = "VERIFY_EMAIL",
    request_id: str = "",
) -> None:
    # Always print OTP prominently to server stdout for instant developer/testing access
    print(f"\n🔑 ========================================================", flush=True)
    print(f"   VERIFICATION CODE FOR {to_email} ({purpose}): {otp_code}", flush=True)
    print(f"   ========================================================\n", flush=True)

    try:
        template = jinja_env.get_template("otp_email.html")
        html_content = template.render(
            otp_code=otp_code,
            expire_minutes=settings.OTP_EXPIRE_MINUTES,
            purpose=purpose,
        )

        subject = (
            "Your Verification Code" if purpose == "VERIFY_EMAIL" else "Password Reset Code"
        )

        api_key = settings.RESEND_API_KEY
        if api_key and api_key.startswith("re_") and api_key != "re_123456789_placeholder":
            resend.api_key = api_key
            try:
                params = {
                    "from": _get_from_address(fallback_dev=False),
                    "to": [to_email],
                    "subject": f"{subject} - Negentrophi",
                    "html": html_content,
                }
                response = resend.Emails.send(params)
            except Exception as first_err:
                # If unverified domain error, retry with onboarding@resend.dev
                if "domain" in str(first_err).lower() or "verify" in str(first_err).lower():
                    logger.warning(f"Resend domain unverified, retrying with onboarding@resend.dev: {first_err}")
                    params = {
                        "from": _get_from_address(fallback_dev=True),
                        "to": [to_email],
                        "subject": f"{subject} - Negentrophi",
                        "html": html_content,
                    }
                    response = resend.Emails.send(params)
                else:
                    raise first_err

            logger.info(
                "OTP email dispatched via Resend",
                extra={
                    "email": to_email,
                    "purpose": purpose,
                    "request_id": request_id,
                    "resend_id": getattr(response, "id", str(response)),
                },
            )
        else:
            logger.info(
                f"[LOCAL DEV MOCK EMAIL] OTP for {to_email} ({purpose}): {otp_code}",
                extra={"request_id": request_id},
            )
    except Exception as exc:
        logger.error(
            f"Failed to send OTP email to {to_email}: {exc}. Note: On Resend free tier, emails can only be delivered to your verified account email or via onboarding@resend.dev.",
            extra={"request_id": request_id, "email": to_email},
        )


async def send_welcome_email(to_email: str, request_id: str = "") -> None:
    try:
        template = jinja_env.get_template("welcome_email.html")
        html_content = template.render()

        api_key = settings.RESEND_API_KEY
        if api_key and api_key.startswith("re_") and api_key != "re_123456789_placeholder":
            resend.api_key = api_key
            try:
                params = {
                    "from": _get_from_address(fallback_dev=False),
                    "to": [to_email],
                    "subject": "Welcome to Negentrophi NXPI!",
                    "html": html_content,
                }
                response = resend.Emails.send(params)
            except Exception:
                params = {
                    "from": _get_from_address(fallback_dev=True),
                    "to": [to_email],
                    "subject": "Welcome to Negentrophi NXPI!",
                    "html": html_content,
                }
                response = resend.Emails.send(params)

            logger.info(
                "Welcome email dispatched via Resend",
                extra={"email": to_email, "request_id": request_id, "resend_id": getattr(response, "id", str(response))},
            )
    except Exception as exc:
        logger.error(
            f"Failed to send welcome email to {to_email}: {exc}",
            extra={"request_id": request_id, "email": to_email},
        )


async def send_client_verification_credentials_email(
    client_email: str,
    company_name: str,
    status_name: str,
    request_id: str = "",
) -> None:
    """Dispatches a formal account verification approval notice with credentials to the client."""
    print(f"\n📧 ========================================================", flush=True)
    print(f"   CLIENT VERIFICATION EMAIL DISPATCHED TO: {client_email}", flush=True)
    print(f"   Company: {company_name} | Status: {status_name}", flush=True)
    print(f"   ========================================================\n", flush=True)

    try:
        api_key = settings.RESEND_API_KEY
        if api_key and api_key.startswith("re_") and api_key != "re_123456789_placeholder":
            resend.api_key = api_key
            html_content = f"""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; rounded: 16px;">
                <h2 style="color: #2563eb;">Organization Onboarding Approved! 🎉</h2>
                <p>Hello,</p>
                <p>Great news! Your enterprise organization <strong>{company_name}</strong> has been officially verified and set to <strong>{status_name}</strong> status by the Negentrophi Compliance Team.</p>
                <p>An email containing your portal login credentials and password will be sent to you shortly.</p>
                <p>Thank you for partnering with Negentrophi NXπ!</p>
            </div>
            """

            try:
                params = {
                    "from": _get_from_address(fallback_dev=False),
                    "to": [client_email],
                    "subject": f"Onboarding Verified & Approved: {company_name}",
                    "html": html_content,
                }
                response = resend.Emails.send(params)
            except Exception:
                params = {
                    "from": _get_from_address(fallback_dev=True),
                    "to": [client_email],
                    "subject": f"Onboarding Verified & Approved: {company_name}",
                    "html": html_content,
                }
                response = resend.Emails.send(params)

            logger.info(
                "Client verification approval email dispatched via Resend",
                extra={"email": client_email, "company": company_name, "status": status_name},
            )
    except Exception as exc:
        logger.error(
            f"Failed to send client verification approval email to {client_email}: {exc}",
            extra={"email": client_email},
        )


async def send_admin_onboarding_notification(
    company_name: str,
    user_email: str,
    country: str,
    doc_type: str,
    action: str = "SUBMITTED",
    discussion_date: str | None = None,
    discussion_time: str | None = None,
    meet_link: str | None = None,
) -> None:
    """Notifies admin email when a client completes or updates onboarding details."""
    admin_email = settings.ADMIN_EMAIL
    print(f"\n🔔 ========================================================", flush=True)
    print(f"   ADMIN NOTIFICATION: Onboarding {action} for {company_name}", flush=True)
    print(f"   Client: {user_email} | Country: {country} | Document: {doc_type}", flush=True)
    if discussion_date and discussion_time:
        print(f"   Discussion Schedule: {discussion_date} at {discussion_time}", flush=True)
    if meet_link:
        print(f"   Google Meet Join Link: {meet_link}", flush=True)
    print(f"   ========================================================\n", flush=True)

    try:
        api_key = settings.RESEND_API_KEY
        if api_key and api_key.startswith("re_") and api_key != "re_123456789_placeholder":
            resend.api_key = api_key
            meet_html = ""
            if meet_link:
                meet_html = f"""
                <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; padding: 12px 16px; border-radius: 8px; margin: 12px 0;">
                    <p style="margin: 0; font-size: 14px; font-weight: bold; color: #1e40af;">🎥 Scheduled Google Meet Discussion</p>
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: #1e3a8a;">Date & Time: {discussion_date or ''} at {discussion_time or ''}</p>
                    <p style="margin: 6px 0 0 0;"><a href="{meet_link}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 8px 14px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 12px;">Join Google Meet</a></p>
                </div>
                """

            html_content = f"""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px;">
                <h2 style="color: #2563eb;">Enterprise Onboarding Notice ({action})</h2>
                <p>Organization <strong>{company_name}</strong> ({user_email}) has {action.lower()} onboarding compliance details.</p>
                <ul>
                    <li><strong>Country:</strong> {country}</li>
                    <li><strong>Document Type:</strong> {doc_type}</li>
                </ul>
                {meet_html}
                <p>Log in to the Admin Operations Console to review: <a href="http://localhost:3000/admin">http://localhost:3000/admin</a></p>
            </div>
            """
            try:
                params = {
                    "from": _get_from_address(fallback_dev=False),
                    "to": [admin_email],
                    "subject": f"[Admin Notice] Onboarding {action}: {company_name}",
                    "html": html_content,
                }
                resend.Emails.send(params)
            except Exception:
                params = {
                    "from": _get_from_address(fallback_dev=True),
                    "to": [admin_email],
                    "subject": f"[Admin Notice] Onboarding {action}: {company_name}",
                    "html": html_content,
                }
                resend.Emails.send(params)
    except Exception as exc:
        logger.error(f"Failed to dispatch admin onboarding notification: {exc}")


async def send_client_onboarding_notification(
    company_name: str,
    client_email: str,
    country: str,
    discussion_date: str | None = None,
    discussion_time: str | None = None,
    meet_link: str | None = None,
) -> None:
    """Sends a confirmation email to the client containing onboarding details and Google Meet link."""
    print(f"\n📧 ========================================================", flush=True)
    print(f"   CLIENT CONFIRMATION: Onboarding Submitted for {company_name}", flush=True)
    print(f"   Client: {client_email} | Country: {country}", flush=True)
    if discussion_date and discussion_time:
        print(f"   Discussion Schedule: {discussion_date} at {discussion_time}", flush=True)
    if meet_link:
        print(f"   Google Meet Join Link: {meet_link}", flush=True)
    print(f"   ========================================================\n", flush=True)

    try:
        api_key = settings.RESEND_API_KEY
        if api_key and api_key.startswith("re_") and api_key != "re_123456789_placeholder":
            resend.api_key = api_key
            meet_html = ""
            if meet_link:
                meet_html = f"""
                <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; padding: 12px 16px; border-radius: 8px; margin: 12px 0;">
                    <p style="margin: 0; font-size: 14px; font-weight: bold; color: #1e40af;">🎥 Your Scheduled Google Meet Consultation</p>
                    <p style="margin: 4px 0 0 0; font-size: 13px; color: #1e3a8a;">Date & Time: {discussion_date or ''} at {discussion_time or ''}</p>
                    <p style="margin: 6px 0 0 0;"><a href="{meet_link}" target="_blank" style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 8px 14px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 12px;">Join Google Meet</a></p>
                </div>
                """

            html_content = f"""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px;">
                <h2 style="color: #2563eb;">Onboarding Details Received</h2>
                <p>Hello,</p>
                <p>Thank you for submitting your onboarding details for <strong>{company_name}</strong>.</p>
                <p>Our compliance team is currently reviewing your profile. Here is a summary of the details you submitted:</p>
                <ul>
                    <li><strong>Country:</strong> {country}</li>
                </ul>
                {meet_html}
                <p>Best regards,<br/>The Negentrophi Team</p>
            </div>
            """
            try:
                params = {
                    "from": _get_from_address(fallback_dev=False),
                    "to": [client_email],
                    "subject": f"Onboarding Details Submitted: {company_name}",
                    "html": html_content,
                }
                resend.Emails.send(params)
            except Exception:
                params = {
                    "from": _get_from_address(fallback_dev=True),
                    "to": [client_email],
                    "subject": f"Onboarding Details Submitted: {company_name}",
                    "html": html_content,
                }
                resend.Emails.send(params)
    except Exception as exc:
        logger.error(f"Failed to dispatch client onboarding notification: {exc}")


async def send_contact_sales_email(
    name: str,
    email: str,
    company: str,
    phone: str | None,
    role: str,
    intent: str,
    message: str | None,
) -> None:
    """Sends a notification email to the admin with contact/sales inquiry details."""
    admin_email = settings.ADMIN_EMAIL
    print(f"\n🔔 ========================================================", flush=True)
    print(f"   CONTACT SALES INQUIRY: {name} ({email}) from {company}", flush=True)
    print(f"   Role: {role} | Intent: {intent} | Phone: {phone or 'N/A'}", flush=True)
    if message:
        print(f"   Message: {message}", flush=True)
    print(f"   ========================================================\n", flush=True)

    try:
        api_key = settings.RESEND_API_KEY
        if api_key and api_key.startswith("re_") and api_key != "re_123456789_placeholder":
            resend.api_key = api_key
            html_content = f"""
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 16px;">
                <h2 style="color: #2563eb;">New Contact / Sales Inquiry</h2>
                <p>A new inquiry was submitted via the website contact form.</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; font-weight: bold; width: 120px;">Name:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; font-weight: bold;">Email:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;"><a href="mailto:{email}">{email}</a></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; font-weight: bold;">Company:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{company}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; font-weight: bold;">Phone:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{phone or 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; font-weight: bold;">Role:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{role}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7; font-weight: bold;">Inquiry Type:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #edf2f7;">{intent}</td>
                    </tr>
                </table>
                <div style="margin-top: 20px; padding: 15px; background-color: #f7fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
                    <p style="margin: 0 0 8px 0; font-weight: bold; color: #4a5568;">Message:</p>
                    <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #2d3748; white-space: pre-wrap;">{message or '(No message details provided)'}</p>
                </div>
            </div>
            """
            try:
                params = {
                    "from": _get_from_address(fallback_dev=False),
                    "to": [admin_email],
                    "subject": f"[Inquiry] {intent.capitalize()}: {name} from {company}",
                    "html": html_content,
                }
                resend.Emails.send(params)
            except Exception:
                params = {
                    "from": _get_from_address(fallback_dev=True),
                    "to": [admin_email],
                    "subject": f"[Inquiry] {intent.capitalize()}: {name} from {company}",
                    "html": html_content,
                }
                resend.Emails.send(params)
    except Exception as exc:
        logger.error(f"Failed to dispatch contact sales email notification: {exc}")

