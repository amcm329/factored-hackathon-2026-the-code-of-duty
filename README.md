# Factored AI Frontend Demo

Local React/Vite frontend for the Factored AI transaction-dispute prototype.

## Compatible environment

- Node.js 16.13.1 or newer within Node 16
- npm 8.x
- Vite 4.5.14

## Run locally

```bash
npm install
npm run dev
```

Open the URL shown by Vite, normally:

```text
http://localhost:5173
```

## Demo behavior

- The application starts in **Guest mode**. There is no login wall.
- General dispute questions can be asked without authentication.
- If the user asks for personal transaction information, a secure-login modal appears.
- The right-side transaction panel is hidden until authentication.
- Hard-coded demo credentials:
  - Customer ID: `CUST_1042`
  - Password: `demo123`
- After login, the app shows the hard-coded Urban Outfitters transaction and dispute actions.
- Transactions, Case Status, and Settings navigation items open a **Work in Progress** page.
- English, Spanish, and Portuguese are available.

## Current scope

This is frontend-only. Authentication, banking data, model inference, dispute registration, and AWS services are still mocked/hard-coded.

## Demo security flow

The demo starts in guest mode. A normal header sign-in authenticates the demo user but does not reveal transaction/card details. When a personal dispute request triggers authentication, the UI simulates transaction validation after login. Personal transaction/card details are displayed only after both authentication and simulated dispute-transaction validation succeed.

## Demo session persistence

The local demo stores only the simulated authentication state, selected language, and simulated transaction-validation state in `sessionStorage`.

- Refreshing the page keeps the current demo login session.
- Explicit Sign out clears the demo authentication and validation state.
- Closing the browser tab/window ends the browser session and the next session starts as Guest.
- This is frontend-only demo behavior. Production authentication will be replaced by Amazon Cognito/session tokens; no password is stored in browser session storage.


## Composer behavior

The message box grows automatically as you type. After reaching its maximum height, it shows a vertical scrollbar. Press Enter to send and Shift+Enter for a new line.


## v6 chat scrolling fix

The conversation area now has a real vertical scrollbar once messages exceed the visible chat area. The message list has a bounded viewport height and automatically scrolls to the newest message. The growing composer from v5 remains unchanged.
