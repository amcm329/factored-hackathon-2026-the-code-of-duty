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
  send_satisfaction_feedback,
  upload_evidence_pdf,
} from '../api'
import {
  get_current_username,
  has_auth_session,
  sign_in,
  sign_out,
} from '../auth'

const language_storage_key = 'factored_language'
const max_evidence_files = 3

const personal_dispute_signals = [
  "i don't recognize",
  'i do not recognize',
  'i want to dispute',
  'i need to dispute',
  'not my transaction',
  'not my purchase',
  'unauthorized transaction',
  'unauthorised transaction',
  'unauthorized charge',
  'unauthorised charge',
  'my card was charged',
  'charged my card',
  'dispute this transaction',
  'open a dispute',
  "this transaction isn't mine",
  'this transaction is not mine',
  'no reconozco',
  'quiero disputar',
  'necesito disputar',
  'no es mi transacción',
  'no es mi transaccion',
  'no es mi compra',
  'cargo no reconocido',
  'transacción no reconocida',
  'transaccion no reconocida',
  'compra no reconocida',
  'cargaron mi tarjeta',
  'me cobraron',
  'disputar esta transacción',
  'disputar esta transaccion',
  'abrir una disputa',
  'não reconheço',
  'quero contestar',
  'preciso contestar',
  'nao reconheco',
  'não é minha transação',
  'nao e minha transacao',
  'transação não reconhecida',
  'transacao nao reconhecida',
  'compra não reconhecida',
  'compra nao reconhecida',
  'me cobraram',
  'cobraram meu cartão',
  'cobraram meu cartao',
  'contestar esta transação',
  'contestar esta transacao',
  'abrir uma contestação',
  'abrir uma contestacao',
]

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
    validatedBadge: 'Selected transaction',
    validationPendingTitle: 'No transaction selected',
    validationPendingText: 'A transaction will be selected explicitly before a dispute is opened.',
    selectTransaction: 'Select the transaction you want to dispute.',
    select: 'Select',
    openDispute: 'Open dispute',
    placeholder: 'Ask about a transaction dispute...',
    details: 'Transaction Details',
    merchant: 'Merchant',
    amount: 'Amount',
    date: 'Date',
    location: 'Location',
    card: 'Product',
    noTransactionTitle: 'Personal transaction details are hidden',
    noTransactionText: 'Sign in when you need access to your personal banking information.',
    satisfactionQuestion: 'Did this resolve your issue?',
    yes: 'Yes',
    no: 'No',
    noTransactions: 'No transactions were available for selection.',
    evidenceLimit: 'You can attach up to three PDF evidence files.',
    requestFailed: 'The request could not be completed. Please try again.',
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
    validatedBadge: 'Transacción seleccionada',
    validationPendingTitle: 'No hay una transacción seleccionada',
    validationPendingText: 'La transacción se seleccionará explícitamente antes de abrir una disputa.',
    selectTransaction: 'Selecciona la transacción que quieres disputar.',
    select: 'Seleccionar',
    openDispute: 'Abrir disputa',
    placeholder: 'Pregunta sobre una disputa de transacción...',
    details: 'Detalles de la transacción',
    merchant: 'Comercio',
    amount: 'Monto',
    date: 'Fecha',
    location: 'Ubicación',
    card: 'Producto',
    noTransactionTitle: 'Los detalles personales de la transacción están ocultos',
    noTransactionText: 'Inicia sesión cuando necesites acceder a tu información bancaria personal.',
    satisfactionQuestion: '¿Esto resolvió tu problema?',
    yes: 'Sí',
    no: 'No',
    noTransactions: 'No hay transacciones disponibles para seleccionar.',
    evidenceLimit: 'Puedes adjuntar hasta tres archivos PDF como evidencia.',
    requestFailed: 'No se pudo completar la solicitud. Inténtalo de nuevo.',
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
    validatedBadge: 'Transação selecionada',
    validationPendingTitle: 'Nenhuma transação selecionada',
    validationPendingText: 'A transação será selecionada explicitamente antes de abrir uma contestação.',
    selectTransaction: 'Selecione a transação que deseja contestar.',
    select: 'Selecionar',
    openDispute: 'Abrir contestação',
    placeholder: 'Pergunte sobre uma contestação de transação...',
    details: 'Detalhes da transação',
    merchant: 'Estabelecimento',
    amount: 'Valor',
    date: 'Data',
    location: 'Localização',
    card: 'Produto',
    noTransactionTitle: 'Os detalhes pessoais da transação estão ocultos',
    noTransactionText: 'Entre quando precisar acessar suas informações bancárias pessoais.',
    satisfactionQuestion: 'Isso resolveu seu problema?',
    yes: 'Sim',
    no: 'Não',
    noTransactions: 'Não há transações disponíveis para selecionar.',
    evidenceLimit: 'Você pode anexar até três arquivos PDF como evidência.',
    requestFailed: 'Não foi possível concluir a solicitação. Tente novamente.',
  },
}

function looksPersonalDispute(value) {
  const normalized = String(value || '').toLowerCase().replace(/’/g, "'").replace(/\s+/g, ' ').trim()
  return personal_dispute_signals.some((signal) => normalized.includes(signal))
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
  const [evidenceIds, setEvidenceIds] = useState([])
  const [interactionId] = useState(() => crypto.randomUUID())
  const [isUploadingEvidence, setIsUploadingEvidence] = useState(false)
  const [interactionFinished, setInteractionFinished] = useState(false)
  const [awaitingFeedback, setAwaitingFeedback] = useState(false)
  const [pendingDisputeReason, setPendingDisputeReason] = useState('')
  const [pendingLoginRequest, setPendingLoginRequest] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [transactionsError, setTransactionsError] = useState('')
  const [showTransactionSelection, setShowTransactionSelection] = useState(false)
  const [readyToOpenDispute, setReadyToOpenDispute] = useState(false)
  const composerRef = React.useRef(null)
  const messagesRef = React.useRef(null)
  const welcomeLoadedRef = React.useRef(false)

  function addMessage(from, text, extra = {}) {
    if (!text) return

    setMessages((items) => [...items, {
      from,
      text,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      ...extra,
    }])
  }

  function addBot(text, extra = {}) {
    addMessage('bot', text, extra)
  }

  function addUser(text) {
    addMessage('user', text)
  }

  function currentHistory() {
    return messages
      .filter((message) => !message.feedbackPrompt)
      .map((message) => ({
        role: message.from === 'user' ? 'user' : 'assistant',
        content: message.text,
      }))
  }

  function showError(error) {
    addBot(error?.message || t.requestFailed)
  }

  async function loadTransactions() {
    if (!authenticated) return []

    try {
      const result = await list_transactions()
      const formatted = (result.transactions || []).map(formatTransaction).filter(Boolean)
      setTransactions(formatted)
      setTransactionsError('')
      return formatted
    } catch (error) {
      setTransactions([])
      setTransactionsError(error?.message || t.requestFailed)
      return null
    }
  }

  async function enterTransactionSelection(reason) {
    setPendingDisputeReason(reason)
    setAwaitingFeedback(false)
    setReadyToOpenDispute(false)
    onTransaction(null)
    const available = transactions.length ? transactions : await loadTransactions()
    setShowTransactionSelection(true)

    if (available !== null && !available.length) {
      setTransactionsError(t.noTransactions)
    }
  }

  async function processChatMessage(message, history) {
    try {
      const result = await send_chat(
        message,
        language,
        history,
        evidenceIds,
        interactionId,
      )

      if (result.authentication_required) {
        setPendingLoginRequest({ message, history })
        onRequireLogin()
        return
      }

      if (result.response) {
        addBot(result.response)
      }

      if (result.needs_satisfaction_feedback) {
        setPendingDisputeReason(message)
        setAwaitingFeedback(true)
        addBot(t.satisfactionQuestion, { feedbackPrompt: true })
        return
      }

      if (result.needs_transaction_selection) {
        await enterTransactionSelection(message)
      }
    } catch (error) {
      showError(error)
    }
  }

  React.useEffect(() => {
    if (welcomeLoadedRef.current) return

    welcomeLoadedRef.current = true
    get_welcome_message(language)
      .then((result) => addBot(result.message))
      .catch((error) => showError(error))
  }, [])

  React.useEffect(() => {
    if (authenticated) {
      loadTransactions()
    } else {
      setTransactions([])
      setTransactionsError('')
      onTransaction(null)
    }
  }, [authenticated])

  React.useEffect(() => {
    if (!authenticated || !pendingLoginRequest) return

    const request = pendingLoginRequest
    setPendingLoginRequest(null)
    processChatMessage(request.message, request.history)
  }, [authenticated, pendingLoginRequest])

  React.useEffect(() => {
    const container = messagesRef.current

    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }, [messages, showTransactionSelection, readyToOpenDispute])

  function resizeComposer() {
    const textarea = composerRef.current

    if (!textarea) return

    textarea.style.height = '44px'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`
    textarea.style.overflowY = textarea.scrollHeight > 140 ? 'auto' : 'hidden'
  }

  async function handleEvidenceFile(file) {
    if (!file || interactionFinished || awaitingFeedback) return

    if (!authenticated) {
      onRequireLogin()
      return
    }

    if (evidenceIds.length >= max_evidence_files) {
      addBot(t.evidenceLimit)
      return
    }

    if (file.type !== 'application/pdf') {
      addBot('Only PDF evidence is allowed')
      return
    }

    if (file.size > 10 * 1024 * 1024) {
      addBot('PDF must be 10 MB or smaller')
      return
    }

    setIsUploadingEvidence(true)

    try {
      const upload = await request_evidence_upload(file)
      await upload_evidence_pdf(file, upload)
      await process_evidence(upload.evidence_id)
      setEvidenceIds((current) => [...current, upload.evidence_id])
    } catch (error) {
      showError(error)
    } finally {
      setIsUploadingEvidence(false)
    }
  }

  async function submit(event) {
    event.preventDefault()

    const value = input.trim()

    if (!value || interactionFinished || awaitingFeedback) return

    const history = currentHistory()
    addUser(value)
    setInput('')

    if (!authenticated && looksPersonalDispute(value)) {
      setPendingLoginRequest({ message: value, history })
      onRequireLogin()
      return
    }

    await processChatMessage(value, history)
  }

  async function handleFeedback(feedback) {
    if (!awaitingFeedback) return

    try {
      const result = await send_satisfaction_feedback(
        interactionId,
        feedback,
        language,
      )
      addUser(feedback === 'yes' ? t.yes : t.no)
      setAwaitingFeedback(false)

      if (feedback === 'yes') {
        setInteractionFinished(true)
        setShowTransactionSelection(false)
        setReadyToOpenDispute(false)
        return
      }

      if (result.needs_transaction_selection) {
        await enterTransactionSelection(pendingDisputeReason)
      }
    } catch (error) {
      showError(error)
    }
  }

  function selectTransaction(selected) {
    onTransaction(selected)
    setShowTransactionSelection(false)
    setReadyToOpenDispute(true)
  }

  async function openDispute() {
    if (!authenticated) {
      onRequireLogin()
      return
    }

    if (!transaction || !pendingDisputeReason || interactionFinished) return

    try {
      const result = await create_dispute({
        transaction_id: transaction.transaction_id,
        reason: pendingDisputeReason,
        language,
        interaction_id: interactionId,
        evidence_ids: evidenceIds,
      })

      if (result.response) {
        addBot(result.response)
      } else {
        addBot(`${result.dispute.status}: ${result.dispute.dispute_id}`)
      }

      setInteractionFinished(true)
      setReadyToOpenDispute(false)
      setShowTransactionSelection(false)
    } catch (error) {
      showError(error)
    }
  }

  const composerDisabled = interactionFinished || awaitingFeedback

  return (
    <section className="chat-panel">
      <div className="messages" ref={messagesRef}>
        {messages.map((message, index) => (
          <div className={`message-row ${message.from}`} key={`${message.from}-${index}`}>
            {message.from === 'bot' && <div className="bot-avatar"><Bot size={24} /></div>}
            <div className="message-stack">
              <div className={`message-bubble ${message.from}`}>{message.text}</div>
              <span className="message-time">{message.time}</span>
              {message.feedbackPrompt && awaitingFeedback && (
                <div className="feedback-actions">
                  <button className="primary" type="button" onClick={() => handleFeedback('yes')}>{t.yes}</button>
                  <button className="secondary" type="button" onClick={() => handleFeedback('no')}>{t.no}</button>
                </div>
              )}
            </div>
            {message.from === 'user' && <div className="user-mini-avatar"><UserRound size={21} /></div>}
          </div>
        ))}

        {showTransactionSelection && authenticated && !interactionFinished && (
          <div className="transaction-selection">
            <div className="message-bubble bot">{t.selectTransaction}</div>
            {transactionsError && <div className="selection-error">{transactionsError}</div>}
            {transactions.map((item) => (
              <div className="transaction-choice" key={item.transaction_id}>
                <TransactionCard transaction={item} />
                <button className="primary" type="button" onClick={() => selectTransaction(item)}>{t.select}</button>
              </div>
            ))}
          </div>
        )}

        {readyToOpenDispute && transaction && !interactionFinished && (
          <div className="selected-transaction-action">
            <TransactionCard transaction={transaction} />
            <button className="primary" type="button" onClick={openDispute}><FileText size={20} />{t.openDispute}</button>
          </div>
        )}
      </div>

      <form className="composer" onSubmit={submit}>
        <label className="attach-button" aria-label="Attach evidence">
          <Paperclip size={26} />
          <input
            type="file"
            accept="application/pdf"
            hidden
            disabled={isUploadingEvidence || composerDisabled || evidenceIds.length >= max_evidence_files}
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
          disabled={composerDisabled}
        />
        <button type="submit" className="send-button" aria-label="Send" disabled={composerDisabled}><Send size={22} /></button>
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
  const [sessionVersion, setSessionVersion] = useState(0)
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
    setSessionVersion((value) => value + 1)
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
            key={sessionVersion}
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
