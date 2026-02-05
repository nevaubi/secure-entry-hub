

## Private Platform with Authentication

A secure, private platform with email/password authentication and a clean dark-mode dashboard.

---

### 1. Login Page (Landing Page)
- **Clean, centered login form** with email and password fields
- **Dark mode styling** with a minimal, professional appearance
- Sign in and Sign up functionality (toggle between modes)
- Password reset flow
- Error handling with clear user feedback
- No public content - authentication is the only entry point

---

### 2. Supabase Authentication Setup
- Enable email/password authentication
- Configure auth redirects and session management
- Secure session handling with proper auth state listeners

---

### 3. Protected Dashboard
- **Top navigation bar** with:
  - Logo/app name on the left
  - User email display and logout button on the right
- **Home page** - clean empty state, ready for your future content
- Responsive design that works on mobile and desktop
- Protected routes that redirect to login if not authenticated

---

### 4. Route Protection
- Automatic redirect to login for unauthenticated users
- Redirect to dashboard after successful login
- Clean logout flow that returns to login

---

**Visual Style**: Dark mode throughout with clean typography and subtle borders

