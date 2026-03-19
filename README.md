# 📧 Gmail All Mailbox Pro v2.0

**Unified Inbox Manager for 100+ Gmail Accounts**

A powerful, premium desktop application to manage all your Gmail accounts in one place. View, reply, delete, and star messages across multiple accounts with a beautiful, modern interface.

---

## ✨ Features

### 🎯 Core Features
- **� Unified Inbox** - View all emails from 100+ Gmail accounts in one place
- **⚡ Fast Message Loading** - Optimized for speed with background threading
- **🔍 Real-time Search** - Search across all accounts instantly
- **📱 Auto-Sync** - Automatic background sync every 60 seconds
- **🔔 Live Notifications** - Get notified of new emails with toast notifications

### 👤 Account Management
- **➕ Add Single Account** - Add accounts one by one with credentials
- **📁 Bulk Import** - Import all accounts from a folder at once with "➕ Add Selected" and "📥 Import All" options
- **🔐 Connect All** - Authenticate all offline accounts with one click
- **🔄 Token Refresh** - Auto-refresh expired tokens
- **⚙️ Account Manager** - View account status and manage connections

### 📨 Email Actions
- **↩️ Reply** - Reply to emails directly from the app
- **🗑 Delete** - Direct delete to trash (no confirmation popup) - Moves immediately to trash with notification
- **⭐ Star/Unstar** - Mark important emails with star
- **✓ Mark Read** - Manually mark messages as read
- **📧 Open in Gmail** - Open any email in browser
- **● Auto-Read** - Messages automatically marked as read when viewed

### � Smart Filters
- **📥 All Messages** - View all emails from all accounts
- **🔴 Unread** - Show only unread emails
- **⭐ Starred** - Show starred/important emails
- **📤 Sent** - View sent messages
- **🗑 Trash** - View trash/deleted messages

### 🎨 Premium UI
- **🌙 Dark Theme** - Professional dark interface
- **📊 Live Stats** - Real-time account and message statistics
- **🎯 Modern Design** - Premium buttons, animations, and toast notifications
- **📱 Responsive Layout** - Split-pane message viewer
- **● Unread Indicators** - Visual dot indicator for unread messages
- **✓ Read Status** - Shows read/unread status in message detail view

---

## � Getting Started

### Prerequisites
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Installation
1. Clone or download the repository
2. Install dependencies (see above)
3. Run `python main.py`

### First Time Setup
1. **Add Accounts**: Click "➕ Add Account" or "📁 Bulk Import"
2. **Authenticate**: Click "🔐 Connect All" to authenticate all accounts
3. **Sync Messages**: Click "🔄 Sync All Now" to fetch messages
4. **Done!** - Your unified inbox is ready

---

## � Usage Guide

### Adding Accounts

#### Single Account
1. Click **"➕ Add Account"** button
2. Enter account name
3. Select credentials JSON file
4. Click "Add Account"
5. Authenticate when prompted

#### Bulk Import (100+ Accounts)
1. Click **"� Bulk Import"** button
2. Browse to folder containing all credential files
3. Click "Scan Folder" (auto-scans when selecting folder)
4. Select accounts from list
5. Click **"➕ Add Selected"** to add one by one, OR
6. Click **"� Import All"** to add all at once

### Managing Accounts

#### Connect All Accounts
- Click **"🔐 Connect All"** in sidebar
- Automatically authenticates all offline accounts
- Shows progress notifications

#### Account Manager
- Click **"⚙️ Manage Accounts"** in sidebar
- View all accounts with status (Online/Offline)
- Select account and click "🔐 Connect Selected" to authenticate
- Click "🔄 Refresh Status" to update status display

### Reading & Managing Emails

#### View Messages
1. Click **"🔄 Sync All Now"** to fetch latest messages
2. Select message from list to view details
3. Use filters in sidebar to filter by type

#### Reply to Email
1. Select message
2. Click **"↩️ Reply"** button
3. Type your reply
4. Click "Send Reply"

#### Delete Email (Direct Delete - No Confirmation)
1. Select message
2. Click **"🗑 Delete"** button
3. Message is **immediately** moved to trash (no confirmation popup)
4. Toast notification shows "Deleted - Message moved to trash" for 2 seconds

#### Star Email
1. Select message
2. Click **"⭐ Star"** button
3. Click again to unstar

#### Mark as Read
1. Select message
2. Click **"✓ Mark Read"** button
3. Message will be marked as read on Gmail

**Note:** Messages are automatically marked as read when you view them!

---

## � Technical Details

### Authentication
- Supports OAuth 2.0 for Gmail API
- Token-based authentication for existing credentials
- Auto-refresh of expired tokens
- Secure token storage in `%APPDATA%/GmailAllMailbox`

### Data Storage
- **Accounts**: `%APPDATA%/GmailAllMailbox/accounts.json`
- **Tokens**: `%APPDATA%/GmailAllMailbox/token_*.json`
- **Cache**: `%APPDATA%/GmailAllMailbox/cache/`
- **Settings**: `%APPDATA%/GmailAllMailbox/settings.json`

### Auto-Sync Settings
- Default interval: 60 seconds
- Checks for new unread messages
- Shows toast notifications for new emails
- Can be disabled in settings

---

## �️ Troubleshooting

### Account Shows "Offline"
1. Click **"🔐 Connect All"** in sidebar
2. Or open **"⚙️ Manage Accounts"** and connect individually
3. Check credentials file is valid

### Messages Not Loading
1. Ensure accounts are authenticated (show "Online")
2. Click **"🔄 Sync All Now"**
3. Check internet connection

### Bulk Import Not Working
1. Ensure folder contains valid JSON credential files
2. Check files have `.json` extension
3. Verify files contain valid Gmail API credentials
4. Make sure `scan_folder` function completes successfully

### Authentication Errors
1. Delete token file: `%APPDATA%/GmailAllMailbox/token_*.json`
2. Re-authenticate the account
3. Check credentials file format (should be OAuth client secrets or token file)

---

## � File Structure

```
Gmail All Mailbox/
├── main.py              # Main application file
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── credentials/        # Store your credential files here
│   ├── account1_credentials.json
│   ├── account2_credentials.json
│   └── ...
└── %APPDATA%/GmailAllMailbox/  # App data (auto-created)
    ├── accounts.json
    ├── settings.json
    ├── token_*.json
    └── cache/
```

---

## 🔒 Security Notes

- Credential files are NEVER modified or deleted
- Tokens are stored locally on your machine only
- No data is sent to any external servers
- All Gmail API calls use official Google libraries

---

## 🎨 UI Features

### Premium Toast Notifications
- Fade-in/fade-out animations
- Color-coded by type (success, warning, error, info)
- Auto-dismiss after 5 seconds
- Click to dismiss manually

### Modern Button Design
- Hover effects with color transitions
- Flat, modern design
- Color-coded by action type:
  - 🔵 Accent (primary actions)
  - 🟢 Success (import, add)
  - 🔴 Danger (delete)
  - 🟡 Warning (star)
  - ⚫ Panel (secondary actions)

### Message List Features
- Unread messages shown in **bold**
- Read messages in regular font
- Real-time message count
- Sort by date (newest first)

---

## 🌟 Tips & Tricks

1. **Quick Add**: Use "📁 Bulk Import" to add all 100+ accounts at once
2. **Auto-Connect**: Click "🔐 Connect All" after bulk import to authenticate all
3. **Smart Search**: Use search box to find emails across all accounts
4. **Notifications**: Keep auto-sync enabled for real-time email alerts
5. **Star Important**: Star emails to find them easily later

---

## � Bug Reports & Issues

If you encounter any issues:
1. Check the troubleshooting section above
2. Verify all dependencies are installed
3. Check credential file format
4. Try deleting token files and re-authenticating

---

## � License

This software is for personal use with your own Gmail accounts.

---

## 🙏 Credits

Built with:
- Python 3.x
- Tkinter (GUI)
- Google Gmail API
- Google Auth Libraries

---

**Version**: 2.0 PRO  
**Last Updated**: March 2026  
**Status**: ✅ Production Ready

---

# 🎉 Happy Emailing!

Manage all your Gmail accounts like a pro! 🚀