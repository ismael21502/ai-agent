import os
import base64
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from langchain_core.tools import tool
from bs4 import BeautifulSoup

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------
# "BuiltInTools/Google/credentials.json"
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]

USER_ID = "me"

def htmlToText(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)

# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------

def getGmailService():
    """
    Authenticate the user and return an authenticated Gmail API service.
    On the first execution:
        - Opens a browser
        - Requests Google authorization
        - Saves the refresh token in token.json
    On subsequent executions:
        - Reuses token.json
        - Refreshes the access token when necessary
    """
    creds = None
    # Existing token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            TOKEN_FILE,
            SCOPES
        )
    # Token expired or missing
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"No se encontró {CREDENTIALS_FILE}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE,
                SCOPES
            )
            creds = flow.run_local_server(
                port=0
            )
        # Save credentials for future executions
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build(
        "gmail",
        "v1",
        credentials=creds
    )


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _getHeader(headers, name):
    """
    Get a header value from Gmail message headers.
    """
    name = name.lower()
    for header in headers:
        if header["name"].lower() == name:
            return header["value"]

    return None


def _decodeBody(data):
    """
    Decode Gmail's base64url encoded body.
    """
    if not data:
        return ""
    return base64.urlsafe_b64decode(
        data.encode("UTF-8")
    ).decode(
        "UTF-8",
        errors="replace"
    )


def _extractBody(payload):
    """
    Extract plain-text body from a Gmail message payload.
    Handles:
        - plain text messages
        - multipart messages
        - nested multipart messages
    """
    mime_type = payload.get("mimeType")
    body = payload.get("body", {})
    # Simple text/plain message
    if mime_type == "text/plain":
        return _decodeBody(body.get("data"))
    # Multipart message
    parts = payload.get("parts", [])
    for part in parts:
        result = _extractBody(part)
        if result:
            return result
    # Fallback
    if body.get("data"):
        return _decodeBody(body["data"])
    return ""


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

def searchMessages(
    query: str,
    maxResults: int = 5
):
    """
    Search Gmail using Gmail's native search syntax.
    Examples:
        from:amazon.com
        is:unread
        subject:invoice
        newer_than:7d
        from:amazon.com is:unread
    """
    service = getGmailService()
    response = service.users().messages().list(
        userId=USER_ID,
        q=query,
        maxResults=maxResults
    ).execute()
    messages = response.get("messages", [])
    results = []
    for message in messages:
        message_id = message["id"]
        metadata = service.users().messages().get(
            userId=USER_ID,
            id=message_id,
            format="metadata",
            metadataHeaders=[
                "From",
                "To",
                "Subject",
                "Date"
            ]
        ).execute()
        headers = metadata.get(
            "payload",
            {}
        ).get(
            "headers",
            []
        )
        results.append({
            "id": message_id,
            # "thread_id": metadata.get("threadId"),
            "from": _getHeader(headers, "From"),
            "to": _getHeader(headers, "To"),
            "subject": _getHeader(headers, "Subject"),
            "date": _getHeader(headers, "Date"),
            # "labels": metadata.get("labelIds", [])
        })
    return results

# ---------------------------------------------------------
# READ MESSAGE
# ---------------------------------------------------------

def openMessage(message_id: str):
    """
    Read a complete Gmail message.
    """
    service = getGmailService()
    message = service.users().messages().get(
        userId=USER_ID,
        id=message_id,
        format="full"
    ).execute()
    payload = message.get("payload", {})
    headers = payload.get(
        "headers",
        []
    )
    return {
        "id": message["id"],
        "thread_id": message.get("threadId"),
        "from": _getHeader(headers, "From"),
        "to": _getHeader(headers, "To"),
        "cc": _getHeader(headers, "Cc"),
        "bcc": _getHeader(headers, "Bcc"),
        "subject": _getHeader(headers, "Subject"),
        "date": _getHeader(headers, "Date"),
        "body": htmlToText(_extractBody(payload)),
        "labels": message.get("labelIds", [])
    }

# ---------------------------------------------------------
# TRASH
# ---------------------------------------------------------

def trashMessage(message_id: str):
    """
    Move a message to Gmail Trash.
    This is NOT permanent deletion.
    """
    service = getGmailService()
    result = service.users().messages().trash(
        userId=USER_ID,
        id=message_id
    ).execute()
    return {
        "success": True,
        "message_id": result["id"],
        "action": "trash"
    }


# ---------------------------------------------------------
# UNTRASH
# ---------------------------------------------------------

def untrashMessage(message_id: str):
    """
    Restore a message from Gmail Trash.
    """

    service = getGmailService()

    result = service.users().messages().untrash(
        userId=USER_ID,
        id=message_id
    ).execute()

    return {
        "success": True,
        "message_id": result["id"],
        "action": "untrash"
    }


# ---------------------------------------------------------
# MODIFY LABELS
# ---------------------------------------------------------

def modifyMessage(
    message_id: str,
    add_labels=None,
    remove_labels=None
):
    """
    Add/remove Gmail labels.
    Examples:
        mark as read:
            remove_labels=["UNREAD"]
        mark as unread:
            add_labels=["UNREAD"]
        archive:
            remove_labels=["INBOX"]
    """
    service = getGmailService()

    body = {
        "addLabelIds": add_labels or [],
        "removeLabelIds": remove_labels or []
    }

    result = service.users().messages().modify(
        userId=USER_ID,
        id=message_id,
        body=body
    ).execute()

    return {
        "success": True,
        "message_id": result["id"],
        "labels": result.get("labelIds", [])
    }

def markAsRead(message_id: str):
    return modifyMessage(
        message_id,
        remove_labels=["UNREAD"]
    )

def markAsUnread(message_id: str):
    return modifyMessage(
        message_id,
        add_labels=["UNREAD"]
    )

def archiveMessage(message_id: str):
    return modifyMessage(
        message_id,
        remove_labels=["INBOX"]
    )

# ---------------------------------------------------------
# CREATE DRAFT
# ---------------------------------------------------------

def createDraft(
    to,
    subject: str,
    body: str,
    cc=None,
    bcc=None
):
    """
    Create a Gmail draft.
    'to', 'cc' and 'bcc' can be:
        - a string
        - a list of strings
    """
    service = getGmailService()
    if isinstance(to, str):
        to = [to]
    if isinstance(cc, str):
        cc = [cc]
    if isinstance(bcc, str):
        bcc = [bcc]
    message = EmailMessage()
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    message.set_content(body)
    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()
    gmail_message = {
        "raw": encoded_message
    }
    draft = service.users().drafts().create(
        userId=USER_ID,
        body={
            "message": gmail_message
        }
    ).execute()
    return {
        "success": True,
        "draft_id": draft["id"],
        "message_id": draft["message"]["id"],
        "thread_id": draft["message"].get("threadId")
    }


# ---------------------------------------------------------
# READ DRAFT
# ---------------------------------------------------------

def readDraft(draft_id: str):
    """
    Retrieve a draft.
    """
    service = getGmailService()
    draft = service.users().drafts().get(
        userId=USER_ID,
        id=draft_id,
        format="full"
    ).execute()
    message = draft["message"]
    payload = message.get("payload", {})
    headers = payload.get(
        "headers",
        []
    )
    return {
        "draft_id": draft["id"],
        "message_id": message["id"],
        "thread_id": message.get("threadId"),
        "from": _getHeader(headers, "From"),
        "to": _getHeader(headers, "To"),
        "cc": _getHeader(headers, "Cc"),
        "bcc": _getHeader(headers, "Bcc"),
        "subject": _getHeader(headers, "Subject"),
        "body": _extractBody(payload)
    }

# ---------------------------------------------------------
# SEND DRAFT
# ---------------------------------------------------------

def sendDraft(draft_id: str):
    """
    Send an existing Gmail draft.
    """
    service = getGmailService()
    result = service.users().drafts().send(
        userId=USER_ID,
        body={
            "id": draft_id
        }
    ).execute()
    return {
        "success": True,
        "message_id": result["id"],
        "thread_id": result.get("threadId"),
        "action": "send"
    }


# ---------------------------------------------------------
# DIRECT SEND
# ---------------------------------------------------------

def sendMessage(
    to,
    subject: str,
    body: str,
    cc=None,
    bcc=None
):
    """
    Send an email directly without creating a draft first.
    For an AI agent, I recommend using createDraft()
    + sendDraft() instead.
    """
    service = getGmailService()
    if isinstance(to, str):
        to = [to]
    if isinstance(cc, str):
        cc = [cc]
    if isinstance(bcc, str):
        bcc = [bcc]
    message = EmailMessage()
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    if cc:
        message["Cc"] = ", ".join(cc)
    if bcc:
        message["Bcc"] = ", ".join(bcc)
    message.set_content(body)
    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()
    result = service.users().messages().send(
        userId=USER_ID,
        body={
            "raw": encoded_message
        }
    ).execute()
    return {
        "success": True,
        "message_id": result["id"],
        "thread_id": result.get("threadId"),
        "action": "send"
    }

@tool 
def getEmails(query: str, maxResults: int = 5):
    """Search Gmail messages using Gmail's search syntax.
    Args:
        query: Gmail search query, such as "from:amazon.com",
            "is:unread", or "from:amazon.com is:unread".
        maxResults: Maximum number of messages to return (max. 10).
    Returns:
        dict containing the search results and message metadata.
    """
    MAX_RESULTS = 10
    results = searchMessages(query, min(maxResults, MAX_RESULTS))

    return {
        "success": True,
        "query": query,
        "count": len(results),
        "messages": results
    }

@tool
def deleteEmail(messageId: str):
    """Move a Gmail message to the trash.
    This operation is reversible. It does not permanently delete the message.
    The message can be restored from the trash using the untrash operation.
    Args:
        messageId: The unique ID of the Gmail message to move to trash.
    Returns:
        Dictionary containing the operation status and message ID.
    """
    result = trashMessage(messageId)
    return result

@tool
def readEmail(messageId: str):
    """Read a complete Gmail message.
    Args:
        messageId: The unique ID of the Gmail message to read.
    Returns:
        Dictionary containing the message metadata and body content.
    """
    result = openMessage(messageId)
    return result

@tool 
def createEmail(to,
    subject: str,
    body: str,
    cc=None,
    bcc=None):
    """Create a Gmail draft.
    Args: 
        to: Recipient email address(es) as a string or list of strings.
        subject: Subject of the email.
        body: Body content of the email.
        cc: Optional; CC recipient email address(es) as a string or list of strings.
        bcc: Optional; BCC recipient email address(es) as a string or list of strings.
    Returns:
        Dictionary containing the draft ID, message ID, and thread ID."""
    return createDraft(to, subject, body, cc, bcc)

@tool 
def sendEmail(draft_id: str):
    """Send an existing Gmail draft.
    Args:
        draft_id: The unique ID of the Gmail draft to send.
    Returns:
        Dictionary containing the operation status and message ID.
    """
    return sendDraft(draft_id)
# ---------------------------------------------------------
# SIMPLE TEST
# ---------------------------------------------------------

if __name__ == "__main__":
    try:
        print("Conectando a Gmail...")
        service = getGmailService()
        print("Conexión correcta.")
        print("\nÚltimos correos:")
        # emails = searchMessages(
        #     "after:2026/09/02 before:2026/09/03",
        #     maxResults=15
        # )
        emails = [openMessage("1a0634ff37e76c9b")]
        print(emails)
        for email in emails:
            print(
                f"\nID: {email['id']}"
                f"\nFrom: {email['from']}"
                f"\nSubject: {email['subject']}"
                f"\nDate: {email['date']}"
            )
    except HttpError as error:
        print(
            f"Error de Gmail API: {error}"
        )
    except Exception as error:
        print(
            f"Error: {error}"
        )