"""Purpose: Build the HTML and plain-text bodies for transactional email.

Dependencies: none.
Used by: app.services.auth when sending a login code.

Colors and type come from the design system so the email matches the product.
Email clients are unreliable with stylesheets, so everything is inline.
"""

from __future__ import annotations

PRIMARY = "#06b6e9"
NAVY = "#0b1f33"
GREY_600 = "#727272"
GREY_200 = "#eeeeee"
BACKGROUND = "#fafafa"

FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, Helvetica, Arial, sans-serif"
)


def login_code_subject(code: str) -> str:
    # Putting the code in the subject lets people read it from a notification.
    return f"{code} is your verification code"


def login_code_text(code: str, *, minutes: int) -> str:
    """Plain-text fallback, for clients that refuse HTML."""

    return (
        "Your verification code\n\n"
        f"{code}\n\n"
        f"This code expires in {minutes} minutes. "
        "If you did not request it, you can ignore this email.\n"
    )


def login_code_html(code: str, *, minutes: int) -> str:
    """The branded code email.

    Table-based and inline-styled on purpose: that is what survives Outlook and
    Gmail. The code is spaced out so it is easy to read off a phone.
    """

    spaced = " ".join(code)
    return f"""<!doctype html>
<html lang="en">
  <body style="margin:0;padding:0;background:{BACKGROUND};font-family:{FONT_STACK};">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:{BACKGROUND};padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="max-width:480px;background:#ffffff;border:1px solid {GREY_200};
                        border-radius:16px;padding:40px 32px;">
            <tr>
              <td align="center" style="padding-bottom:8px;">
                <span style="display:inline-block;width:48px;height:48px;border-radius:999px;
                             background:{PRIMARY};color:#ffffff;font-size:24px;line-height:48px;
                             text-align:center;">&#10003;</span>
              </td>
            </tr>
            <tr>
              <td align="center"
                  style="padding-bottom:8px;font-size:22px;line-height:28px;font-weight:600;color:{NAVY};">
                Your verification code
              </td>
            </tr>
            <tr>
              <td align="center"
                  style="padding-bottom:24px;font-size:14px;line-height:22px;color:{GREY_600};">
                Enter this code to continue as a guarantor.
              </td>
            </tr>
            <tr>
              <td align="center" style="padding-bottom:24px;">
                <div style="display:inline-block;background:#e6f8fe;border-radius:12px;
                            padding:16px 24px;font-size:32px;line-height:40px;font-weight:700;
                            letter-spacing:6px;color:{NAVY};">
                  {spaced}
                </div>
              </td>
            </tr>
            <tr>
              <td align="center"
                  style="font-size:14px;line-height:22px;color:{GREY_600};">
                This code expires in {minutes} minutes.
              </td>
            </tr>
            <tr>
              <td align="center"
                  style="padding-top:24px;border-top:1px solid {GREY_200};margin-top:24px;
                         font-size:12px;line-height:18px;color:{GREY_600};">
                If you did not request this code, you can safely ignore this email.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
