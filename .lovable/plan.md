

## Remove Sign-Up Functionality

Since your account (admin@nevaubi.com) is already created and you want to keep this platform private, I'll remove all sign-up related options from the login page.

---

### Changes to Login Page

**Remove:**
- The `signup` mode from the AuthMode type
- The "Don't have an account? Sign up" link
- The sign-up form handling logic
- The "Create account" title/description variants

**Keep:**
- Sign-in functionality (email/password login)
- Password reset functionality (in case you forget your password)
- "Forgot password?" link

---

### Files to Modify

| File | Change |
|------|--------|
| `src/pages/Login.tsx` | Remove signup mode, related UI elements, and signup handling code |

---

### Result

The login page will only show:
- Email and password fields
- "Sign in" button
- "Forgot password?" link

No one will be able to create new accounts through the UI.

---

### Technical Details

The `signUp` function will remain in the `useAuth` hook (it doesn't hurt to keep it), but it won't be accessible from the interface. This is a simple UI change that effectively locks down registration.

