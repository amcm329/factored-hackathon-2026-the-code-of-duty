const cognito_client_id = import.meta.env.VITE_COGNITO_CLIENT_ID
const cognito_endpoint = 'https://cognito-idp.us-east-1.amazonaws.com/'

const id_token_key = 'factored_cognito_id_token'

function decode_jwt_payload(token) {
  try {
    const payload = token.split('.')[1]
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

function token_is_valid(token) {
  const payload = decode_jwt_payload(token)
  return Boolean(payload?.exp && payload.exp * 1000 > Date.now() + 30000)
}

async function cognito_request(target, body) {
  if (!cognito_client_id) {
    throw new Error('VITE_COGNITO_CLIENT_ID is not configured')
  }

  const response = await fetch(cognito_endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-amz-json-1.1',
      'X-Amz-Target': `AWSCognitoIdentityProviderService.${target}`,
    },
    body: JSON.stringify(body),
  })
  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.message || data.__type || 'Cognito authentication failed')
  }

  return data
}

export async function sign_in(username, password) {
  const data = await cognito_request('InitiateAuth', {
    AuthFlow: 'USER_PASSWORD_AUTH',
    ClientId: cognito_client_id,
    AuthParameters: {
      USERNAME: username,
      PASSWORD: password,
    },
  })
  const token = data.AuthenticationResult?.IdToken

  if (!token) {
    throw new Error('Cognito did not return an ID token')
  }

  window.sessionStorage.setItem(id_token_key, token)
  return token
}

export function get_id_token() {
  const token = window.sessionStorage.getItem(id_token_key)
  return token_is_valid(token) ? token : null
}

export function has_auth_session() {
  return Boolean(get_id_token())
}

export function get_current_username() {
  const token = get_id_token()
  const payload = token ? decode_jwt_payload(token) : null

  return (
    payload?.['custom:customer_id']
    || payload?.['cognito:username']
    || ''
  )
}

export function sign_out() {
  window.sessionStorage.removeItem(id_token_key)
}
