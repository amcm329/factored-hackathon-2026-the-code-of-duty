import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Bot,
  CalendarDays,
  ChevronDown,
  CreditCard,
  FileText,
  Globe2,
  LockKeyhole,
  LogIn,
  LogOut,
  MapPin,
  MessageCircle,
  Paperclip,
  Send,
  ShoppingBag,
  UserRound,
  WalletCards,
} from 'lucide-react'
import './styles.css'
import {
  create_dispute,
  get_welcome_message,
  list_transactions,
  process_evidence,
  request_evidence_upload,
  send_chat,
  upload_evidence_pdf,
} from '../api'
import {
  get_current_username,
  has_auth_session,
  sign_in,
  sign_out,
} from '../auth'

const language_storage_key = 'factored_language'

const copy = {
  en: {
    title: 'AI Dispute Assistant',
    subtitle: 'Help with disputed or unrecognized transactions',
    disputes: 'Disputes',
    guest: 'Guest mode',
    guestId: 'Not signed in',
    signedIn: 'Signed in as',
    signIn: 'Sign in',
    logout: 'Sign out',
    loginTitle: 'Secure sign in required',
    loginSubtitle: 'Sign in to access your personal banking information and continue this request.',
    username: 'Customer ID',
    password: 'Password',
    invalid: 'Invalid credentials.',
    cancel: 'Cancel',
    continueSignIn: 'Sign in and continue',
    validatedBadge: 'Validated transaction',
    validationPendingTitle: 'Transaction details not available yet',
    validationPendingText: 'Sign in and select a transaction before opening a dispute.',
    openDispute: 'Open dispute',
    placeholder: 'Ask about a transaction dispute...',
    details: 'Transaction Details',
    merchant: 'Merchant',
    amount: 'Amount',
    date: 'Date',
    location: 'Location',
    card: 'Card',
    noTransactionTitle: 'Personal transaction details are hidden',
    noTransactionText: 'Sign in when you need access to your personal banking information.',
  },
  es: {
    title: 'Asistente de Disputas con IA',
    subtitle: 'Ayuda con transacciones disputadas o no reconocidas',
    disputes: 'Disputas',
    guest: 'Modo invitado',
    guestId: 'Sin iniciar sesión',
    signedIn: 'Sesión iniciada como',
    signIn: 'Iniciar sesión',
    logout: 'Cerrar sesión',
    loginTitle: 'Se requiere inicio de sesión seguro',
    loginSubtitle: 'Inicia sesión para acceder a tu información bancaria personal y continuar con esta solicitud.',
    username: 'ID de cliente',
    password: 'Contraseña',
    invalid: 'Credenciales inválidas.',
    cancel: 'Cancelar',
    continueSignIn: 'Iniciar sesión y continuar',
    validatedBadge: 'Transacción validada',
    validationPendingTitle: 'Los detalles de la transacción aún no están disponibles',
    validationPendingText: 'Inicia sesión y selecciona una transacción antes de abrir una disputa.',
    openDispute: 'Abrir disputa',
    placeholder: 'Pregunta sobre una disputa de transacción...',
    details: 'Detalles de la transacción',
    merchant: 'Comercio',
    amount: 'Monto',
    date: 'Fecha',
    location: 'Ubicación',
    card: 'Tarjeta',
    noTransactionTitle: 'Los detalles personales de la transacción están ocultos',
    noTransactionText: 'Inicia sesión cuando necesites acceder a tu información bancaria personal.',
  },
  pt: {
    title: 'Assistente de Contestação com IA',
    subtitle: 'Ajuda com transações contestadas ou não reconhecidas',
    disputes: 'Contestações',
    guest: 'Modo convidado',
    guestId: 'Não conectado',
    signedIn: 'Conectado como',
    signIn: 'Entrar',
    logout: 'Sair',
    loginTitle: 'Login seguro necessário',
    loginSubtitle: 'Entre para acessar suas informações bancárias pessoais e continuar esta solicitação.',
    username: 'ID do cliente',
    password: 'Senha',
    invalid: 'Credenciais inválidas.',
    cancel: 'Cancelar',
    continueSignIn: 'Entrar e continuar',
    validatedBadge: 'Transação validada',
    validationPendingTitle: 'Os detalhes da transação ainda não estão disponíveis',
    validationPendingText: 'Entre e selecione uma transação antes de abrir uma contestação.',
    openDispute: 'Abrir contestação',
    placeholder: 'Pergunte sobre uma contestação de transação...',
    details: 'Detalhes da transação',
    merchant: 'Estabelecimento',
    amount: 'Valor',
    date: 'Data',
    location: 'Localização',
    card: 'Cartão',
    noTransactionTitle: 'Os detalhes pessoais da transação estão ocultos',
    noTransactionText: 'Entre quando precisar acessar suas informações bancárias pessoais.',
  },
}

function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark"><span /><span /></div>
      <div>
        <div className="brand-title">YourBank</div>
        <div className="brand-subtitle">Demo Bank</div>
      </div>
    </div>
  )
}

function LanguageSelect({ language, onChange }) {
  return (
    <div className="language-select-wrap">
      <Globe2 size={17} />
      <select value={language} onChange={(event) => onChange(event.target.value)} aria-label="Language">
        <option value="en">EN — English</option>
        <option value="es">ES — Español</option>
        <option value="pt">PT — Português</option>
      </select>
      <ChevronDown size={15} className="select-chevron" />
    </div>
  )
}

function LoginModal({ t, onClose, onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()

    try {
      await onLogin(username, password)
    } catch {
      setError(t.invalid)
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <div className="login-modal" role="dialog" aria-modal="true" aria-labelledby="login-title">
        <div className="login-icon"><LockKeyhole size={30} /></div>
        <h2 id="login-title">{t.loginTitle}</h2>
        <p>{t.loginSubtitle}</p>
        <form onSubmit={submit} className="login-form">
          <label>
            {t.username}
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          </label>
          <label>
            {t.password}
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
          </label>
          {error && <div className="login-error">{error}</div>}
          <div className="login-actions">
            <button type="button" className="secondary" onClick={onClose}>{t.cancel}</button>
            <button type="submit" className="primary"><LogIn size={19} />{t.continueSignIn}</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function Sidebar({ t }) {
  return (
    <aside className="sidebar">
      <Brand />
      <nav className="nav-list">
        <button className="nav-item active" type="button">
          <MessageCircle size={25} />{t.disputes}
        </button>
      </nav>
    </aside>
  )
}

function Header({ t, language, onLanguage, authenticated, customerId, onLogin, onLogout }) {
  return (
    <header className="topbar">
      <div className="assistant-heading">
        <div className="assistant-icon"><Bot size={34} /></div>
        <div><h1>{t.title}</h1><p>{t.subtitle}</p></div>
      </div>
      <div className="topbar-actions">
        <LanguageSelect language={language} onChange={onLanguage} />
        <div className="topbar-separator" />
        <div className={`user-avatar ${authenticated ? '' : 'guest-avatar'}`}>
          {authenticated ? (customerId || 'CU').slice(0, 2).toUpperCase() : <UserRound size={22} />}
        </div>
        <div className="signed-in">
          <span>{authenticated ? t.signedIn : t.guest}</span>
          <strong>{authenticated ? customerId : t.guestId}</strong>
        </div>
        {authenticated ? (
          <button className="logout-button" onClick={onLogout} title={t.logout}><LogOut size={20} /></button>
        ) : (
          <button className="header-signin" onClick={onLogin}><LogIn size={17} />{t.signIn}</button>
        )}
      </div>
    </header>
  )
}

function formatTransaction(raw) {
  if (!raw) return null

  const date = raw.transaction_date ? new Date(raw.transaction_date) : null

  return {
    transaction_id: raw.transaction_id,
    merchant: raw.merchant_name || raw.transaction_category || raw.transaction_type || '',
    category: raw.merchant_category || raw.transaction_category || '',
    amount: `${raw.currency || ''} ${raw.amount ?? ''}`.trim(),
    date: date && !Number.isNaN(date.getTime()) ? date.toLocaleDateString() : '',
    time: date && !Number.isNaN(date.getTime()) ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
    location: [raw.transaction_city, raw.transaction_country].filter(Boolean).join(', '),
    channel: raw.channel || '',
    card: raw.product_id || '',
  }
}

function TransactionCard({ transaction }) {
  if (!transaction) return null

  return (
    <div className="transaction-card">
      <div className="transaction-card-left">
        <div className="merchant-icon"><ShoppingBag size={27} /></div>
        <div><strong>{transaction.merchant}</strong><span>{transaction.category}</span></div>
      </div>
      <div className="transaction-card-right">
        <strong>{transaction.amount}</strong><span>{transaction.date}</span><span>{transaction.time}</span>
      </div>
    </div>
  )
}

function DetailRow({ icon, label, children }) {
  return (
    <div className="detail-row">
      <div className="detail-icon">{icon}</div>
      <div className="detail-copy"><span>{label}</span>{children}</div>
    </div>
  )
}

function TransactionDetails({ t, authenticated, transaction, onLogin }) {
  if (!authenticated) {
    return (
      <aside className="details-panel locked-details">
        <div className="locked-details-icon"><LockKeyhole size={31} /></div>
        <h2>{t.noTransactionTitle}</h2>
        <p>{t.noTransactionText}</p>
        <button className="primary details-signin" onClick={onLogin}><LogIn size={18} />{t.signIn}</button>
      </aside>
    )
  }

  if (!transaction) {
    return (
      <aside className="details-panel locked-details">
        <div className="locked-details-icon"><LockKeyhole size={31} /></div>
        <h2>{t.validationPendingTitle}</h2>
        <p>{t.validationPendingText}</p>
      </aside>
    )
  }

  return (
    <aside className="details-panel">
      <div className="validated-badge">{t.validatedBadge}</div>
      <h2>{t.details}</h2>
      <div className="merchant-summary">
        <div className="merchant-icon large"><ShoppingBag size={30} /></div>
        <div><span>{t.merchant}</span><strong>{transaction.merchant}</strong><small>{transaction.category}</small></div>
      </div>
      <DetailRow icon={<WalletCards size={23} />} label={t.amount}><strong>{transaction.amount}</strong></DetailRow>
      <DetailRow icon={<CalendarDays size={23} />} label={t.date}><strong>{transaction.date}</strong><small>{transaction.time}</small></DetailRow>
      <DetailRow icon={<MapPin size={23} />} label={t.location}><strong>{transaction.location}</strong><small>{transaction.channel}</small></DetailRow>
      <DetailRow icon={<CreditCard size={23} />} label={t.card}><strong>{transaction.card}</strong></DetailRow>
    </aside>
  )
}

function Chat({ t, language, authenticated, transaction, onTransaction, onRequireLogin }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [evidence_ids, setEvidenceIds] = useState([])
  const [interactionId] = useState(() => crypto.randomUUID())
  const [isUploadingEvidence, setIsUploadingEvidence] = useState(false)
  const [interactionFinished, setInteractionFinished] = useState(false)
  const composerRef = React.useRef(null)
  const messagesRef = React.useRef(null)

  function addBot(text) {
    if (!text) return

    setMessages((items) => [...items, {
      from: 'bot',
      text,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }])
  }

  React.useEffect(() => {
    get_welcome_message(language)
      .then((result) => {
        setMessages([{
          from: 'bot',
          text: result.message,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }])
      })
      .catch(() => setMessages([]))
  }, [language])

  React.useEffect(() => {
    if (!authenticated) {
      onTransaction(null)
      return
    }

    list_transactions()
      .then((result) => {
        onTransaction(formatTransaction(result.transactions?.[0]))
      })
      .catch(() => onTransaction(null))
  }, [authenticated])

  React.useEffect(() => {
    const container = messagesRef.current

    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }, [messages])

  function resizeComposer() {
    const textarea = composerRef.current

    if (!textarea) return

    textarea.style.height = '44px'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`
    textarea.style.overflowY = textarea.scrollHeight > 140 ? 'auto' : 'hidden'
  }

  async function handleEvidenceFile(file) {
    if (!file || interactionFinished) return

    if (!authenticated) {
      onRequireLogin()
      return
    }

    if (file.type !== 'application/pdf') {
      throw new Error('Only PDF evidence is allowed')
    }

    if (file.size > 10 * 1024 * 1024) {
      throw new Error('PDF must be 10 MB or smaller')
    }

    setIsUploadingEvidence(true)

    try {
      const upload = await request_evidence_upload(file)
      await upload_evidence_pdf(file, upload)
      await process_evidence(upload.evidence_id, language)
      setEvidenceIds((current) => [...current, upload.evidence_id])
    } finally {
      setIsUploadingEvidence(false)
    }
  }

  async function submit(event) {
    event.preventDefault()

    const value = input.trim()

    if (!value || interactionFinished) return

    const history = messages.map((message) => ({
      role: message.from === 'user' ? 'user' : 'assistant',
      content: message.text,
    }))

    setMessages((items) => [...items, {
      from: 'user',
      text: value,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }])
    setInput('')

    const result = await send_chat(
      value,
      language,
      history,
      evidence_ids,
      interactionId,
    )
    addBot(result.response)
  }

  async function openDispute() {
    if (!authenticated) {
      onRequireLogin()
      return
    }

    if (!transaction) return

    const lastUserMessage = [...messages].reverse().find((message) => message.from === 'user')

    if (!lastUserMessage?.text) return

    const result = await create_dispute({
      transaction_id: transaction.transaction_id,
      reason: lastUserMessage.text,
      language,
      interaction_id: interactionId,
    })

    if (result.response) {
      addBot(result.response)
    } else {
      addBot(`${result.dispute.status}: ${result.dispute.dispute_id}`)
    }

    if (result.interaction_finished) {
      setInteractionFinished(true)
    }
  }

  return (
    <section className="chat-panel">
      <div className="messages" ref={messagesRef}>
        {messages.map((message, index) => (
          <div className={`message-row ${message.from}`} key={`${message.from}-${index}`}>
            {message.from === 'bot' && <div className="bot-avatar"><Bot size={24} /></div>}
            <div className="message-stack">
              <div className={`message-bubble ${message.from}`}>{message.text}</div>
              <span className="message-time">{message.time}</span>
              {message.from === 'bot' && transaction && authenticated && index === messages.length - 1 && !interactionFinished && (
                <>
                  <TransactionCard transaction={transaction} />
                  <div className="transaction-actions">
                    <button className="primary" onClick={openDispute}><FileText size={20} />{t.openDispute}</button>
                  </div>
                </>
              )}
            </div>
            {message.from === 'user' && <div className="user-mini-avatar"><UserRound size={21} /></div>}
          </div>
        ))}
      </div>

      <form className="composer" onSubmit={submit}>
        <label className="attach-button" aria-label="Attach evidence">
          <Paperclip size={26} />
          <input
            type="file"
            accept="application/pdf"
            hidden
            disabled={isUploadingEvidence || interactionFinished}
            onChange={(event) => {
              const file = event.target.files?.[0]

              if (file) {
                handleEvidenceFile(file)
              }

              event.target.value = ''
            }}
          />
        </label>
        <textarea
          ref={composerRef}
          value={input}
          onChange={(event) => {
            setInput(event.target.value)
            window.requestAnimationFrame(resizeComposer)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              event.currentTarget.form.requestSubmit()
            }
          }}
          placeholder={t.placeholder}
          rows={1}
          aria-label={t.placeholder}
          disabled={interactionFinished}
        />
        <button type="submit" className="send-button" aria-label="Send" disabled={interactionFinished}><Send size={22} /></button>
      </form>
    </section>
  )
}

function App() {
  const [language, setLanguage] = useState(() => window.sessionStorage.getItem(language_storage_key) || 'en')
  const [authenticated, setAuthenticated] = useState(() => has_auth_session())
  const [customerId, setCustomerId] = useState(() => get_current_username())
  const [showLogin, setShowLogin] = useState(false)
  const [transaction, setTransaction] = useState(null)
  const t = copy[language]

  function changeLanguage(value) {
    window.sessionStorage.setItem(language_storage_key, value)
    setLanguage(value)
  }

  async function login(username, password) {
    await sign_in(username, password)
    setAuthenticated(true)
    setCustomerId(get_current_username())
    setShowLogin(false)
  }

  function logout() {
    sign_out()
    setAuthenticated(false)
    setCustomerId('')
    setTransaction(null)
  }

  return (
    <div className="app-shell">
      <Sidebar t={t} />
      <main className="app-main">
        <Header
          t={t}
          language={language}
          onLanguage={changeLanguage}
          authenticated={authenticated}
          customerId={customerId}
          onLogin={() => setShowLogin(true)}
          onLogout={logout}
        />
        <div className="content-grid">
          <Chat
            key={`${language}-${authenticated}`}
            t={t}
            language={language}
            authenticated={authenticated}
            transaction={transaction}
            onTransaction={setTransaction}
            onRequireLogin={() => setShowLogin(true)}
          />
          <TransactionDetails
            t={t}
            authenticated={authenticated}
            transaction={transaction}
            onLogin={() => setShowLogin(true)}
          />
        </div>
      </main>
      {showLogin && <LoginModal t={t} onClose={() => setShowLogin(false)} onLogin={login} />}
    </div>
  )
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
