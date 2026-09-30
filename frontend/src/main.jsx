import React, { useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Bell,
  Bot,
  CalendarDays,
  ChevronDown,
  Clock3,
  CreditCard,
  FileText,
  Globe2,
  Landmark,
  LockKeyhole,
  LogIn,
  LogOut,
  MapPin,
  MessageCircle,
  Paperclip,
  Send,
  Settings,
  ShoppingBag,
  UserRound,
  WalletCards,
  Wrench,
} from 'lucide-react'
import './styles.css'
import { process_evidence, request_evidence_upload, send_chat, upload_evidence_pdf } from '../api'

const DEMO_USER = {
  username: 'CUST_1042',
  password: 'demo123',
  initials: 'JD',
  customerId: 'CUST_1042',
  country: 'Mexico',
}

const SESSION_KEYS = {
  authenticated: 'factored_demo_authenticated',
  disputeValidated: 'factored_demo_dispute_validated',
  language: 'factored_demo_language',
}

function readSessionBoolean(key) {
  return window.sessionStorage.getItem(key) === 'true'
}

const transaction = {
  merchant: 'Urban Outfitters',
  category: 'Clothing & Apparel',
  amount: '$320.00',
  date: 'May 14, 2024',
  time: '2:37 PM (GMT-6)',
  location: 'México City, MX',
  channel: 'In-store purchase',
  card: 'Visa  •••• 4421',
}

const copy = {
  en: {
    language: 'English',
    title: 'AI Dispute Assistant',
    subtitle: 'Help with disputed or unrecognized transactions',
    disputes: 'Disputes',
    transactions: 'Transactions',
    caseStatus: 'Case Status',
    settings: 'Settings',
    wip: 'Work in Progress',
    guest: 'Guest mode',
    guestId: 'Not signed in',
    signedIn: 'Signed in as',
    signIn: 'Sign in',
    logout: 'Sign out',
    intro: 'Hi. I can help with transaction disputes. You can ask general questions without signing in.',
    genericHelp: 'For a transaction dispute, I can explain the process without accessing your personal banking data.',
    authNeeded: 'I need to verify your identity before I can access your transactions or create a dispute.',
    loginTitle: 'Secure sign in required',
    loginSubtitle: 'Sign in to access your personal banking information and continue this request.',
    username: 'Customer ID',
    password: 'Password',
    loginHint: 'Demo credentials',
    invalid: 'Invalid demo credentials.',
    cancel: 'Cancel',
    continueSignIn: 'Sign in and continue',
    authenticated: 'Identity verified. I am validating the transaction against your account now.',
    validated: 'Dispute transaction validated. The transaction belongs to your account and matches the information provided.',
    validatedBadge: 'Validated transaction',
    validationPendingTitle: 'Transaction details not available yet',
    validationPendingText: 'You are authenticated, but the assistant must validate the disputed transaction before personal card and transaction details are displayed.',
    userExample: 'I don’t recognize the $320 purchase from yesterday.',
    botMsg: 'I found a matching transaction. Would you like to open a dispute case for this purchase?',
    openDispute: 'Open dispute',
    moreDetails: 'Need more details',
    placeholder: 'Ask about a transaction dispute...',
    details: 'Transaction Details',
    merchant: 'Merchant',
    amount: 'Amount',
    date: 'Date',
    location: 'Location',
    card: 'Card',
    hardcodedOpen: 'Demo mode: your dispute was registered successfully. Case ID: DSP-2026-001.',
    hardcodedMore: 'This demo uses hard-coded data. The transaction is an in-store purchase in México City on May 14, 2024.',
    hardcodedFallback: 'Demo mode: I can explain dispute steps or help with the sample transaction.',
    hardcodedStatus: 'Case DSP-2026-001 is currently OPEN in this local demo.',
    wipTitle: 'Work in Progress',
    wipText: 'This section is part of the planned banking experience and is not implemented in this frontend demo yet.',
    backToDisputes: 'Back to disputes',
    noTransactionTitle: 'Personal transaction details are hidden',
    noTransactionText: 'Sign in only when you need the assistant to access your personal banking information.',
  },
  es: {
    language: 'Español',
    title: 'Asistente de Disputas con IA',
    subtitle: 'Ayuda con transacciones disputadas o no reconocidas',
    disputes: 'Disputas',
    transactions: 'Transacciones',
    caseStatus: 'Estado del caso',
    settings: 'Configuración',
    wip: 'En desarrollo',
    guest: 'Modo invitado',
    guestId: 'Sin iniciar sesión',
    signedIn: 'Sesión iniciada como',
    signIn: 'Iniciar sesión',
    logout: 'Cerrar sesión',
    intro: 'Hola. Puedo ayudarte con disputas de transacciones. Puedes hacer preguntas generales sin iniciar sesión.',
    genericHelp: 'Para una disputa de transacción, puedo explicar el proceso sin acceder a tus datos bancarios personales.',
    authNeeded: 'Necesito verificar tu identidad antes de acceder a tus transacciones o crear una disputa.',
    loginTitle: 'Se requiere inicio de sesión seguro',
    loginSubtitle: 'Inicia sesión para acceder a tu información bancaria personal y continuar con esta solicitud.',
    username: 'ID de cliente',
    password: 'Contraseña',
    loginHint: 'Credenciales demo',
    invalid: 'Credenciales demo inválidas.',
    cancel: 'Cancelar',
    continueSignIn: 'Iniciar sesión y continuar',
    authenticated: 'Identidad verificada. Estoy validando la transacción contra tu cuenta.',
    validated: 'Transacción de disputa validada. La transacción pertenece a tu cuenta y coincide con la información proporcionada.',
    validatedBadge: 'Transacción validada',
    validationPendingTitle: 'Los detalles de la transacción aún no están disponibles',
    validationPendingText: 'Tu identidad ya fue verificada, pero el asistente debe validar la transacción disputada antes de mostrar datos personales de la tarjeta y la transacción.',
    userExample: 'No reconozco la compra de $320 de ayer.',
    botMsg: 'Encontré una transacción que coincide. ¿Quieres abrir un caso de disputa para esta compra?',
    openDispute: 'Abrir disputa',
    moreDetails: 'Necesito más detalles',
    placeholder: 'Pregunta sobre una disputa de transacción...',
    details: 'Detalles de la transacción',
    merchant: 'Comercio',
    amount: 'Monto',
    date: 'Fecha',
    location: 'Ubicación',
    card: 'Tarjeta',
    hardcodedOpen: 'Modo demo: tu disputa fue registrada correctamente. Caso: DSP-2026-001.',
    hardcodedMore: 'Esta demo usa datos fijos. La compra fue presencial en Ciudad de México el 14 de mayo de 2024.',
    hardcodedFallback: 'Modo demo: puedo explicar el proceso de disputa o ayudarte con la transacción de ejemplo.',
    hardcodedStatus: 'El caso DSP-2026-001 está ABIERTO en esta demo local.',
    wipTitle: 'En desarrollo',
    wipText: 'Esta sección forma parte de la experiencia bancaria planeada y todavía no está implementada en esta demo del frontend.',
    backToDisputes: 'Volver a disputas',
    noTransactionTitle: 'Los detalles personales de la transacción están ocultos',
    noTransactionText: 'Inicia sesión únicamente cuando necesites que el asistente acceda a tu información bancaria personal.',
  },
  pt: {
    language: 'Português',
    title: 'Assistente de Contestação com IA',
    subtitle: 'Ajuda com transações contestadas ou não reconhecidas',
    disputes: 'Contestações',
    transactions: 'Transações',
    caseStatus: 'Status do caso',
    settings: 'Configurações',
    wip: 'Em desenvolvimento',
    guest: 'Modo convidado',
    guestId: 'Não conectado',
    signedIn: 'Conectado como',
    signIn: 'Entrar',
    logout: 'Sair',
    intro: 'Olá. Posso ajudar com contestações de transações. Você pode fazer perguntas gerais sem entrar.',
    genericHelp: 'Para uma contestação, posso explicar o processo sem acessar seus dados bancários pessoais.',
    authNeeded: 'Preciso verificar sua identidade antes de acessar suas transações ou criar uma contestação.',
    loginTitle: 'Login seguro necessário',
    loginSubtitle: 'Entre para acessar suas informações bancárias pessoais e continuar esta solicitação.',
    username: 'ID do cliente',
    password: 'Senha',
    loginHint: 'Credenciais demo',
    invalid: 'Credenciais demo inválidas.',
    cancel: 'Cancelar',
    continueSignIn: 'Entrar e continuar',
    authenticated: 'Identidade verificada. Estou validando a transação na sua conta agora.',
    validated: 'Transação da contestação validada. A transação pertence à sua conta e corresponde às informações fornecidas.',
    validatedBadge: 'Transação validada',
    validationPendingTitle: 'Os detalhes da transação ainda não estão disponíveis',
    validationPendingText: 'Sua identidade foi verificada, mas o assistente precisa validar a transação contestada antes de mostrar dados pessoais do cartão e da transação.',
    userExample: 'Não reconheço a compra de $320 de ontem.',
    botMsg: 'Encontrei uma transação correspondente. Deseja abrir um caso de contestação para esta compra?',
    openDispute: 'Abrir contestação',
    moreDetails: 'Preciso de mais detalhes',
    placeholder: 'Pergunte sobre uma contestação de transação...',
    details: 'Detalhes da transação',
    merchant: 'Estabelecimento',
    amount: 'Valor',
    date: 'Data',
    location: 'Localização',
    card: 'Cartão',
    hardcodedOpen: 'Modo demo: sua contestação foi registrada com sucesso. Caso: DSP-2026-001.',
    hardcodedMore: 'Esta demo usa dados fixos. A compra foi presencial na Cidade do México em 14 de maio de 2024.',
    hardcodedFallback: 'Modo demo: posso explicar o processo de contestação ou ajudar com a transação de exemplo.',
    hardcodedStatus: 'O caso DSP-2026-001 está ABERTO nesta demo local.',
    wipTitle: 'Em desenvolvimento',
    wipText: 'Esta seção faz parte da experiência bancária planejada e ainda não foi implementada nesta demo do frontend.',
    backToDisputes: 'Voltar para contestações',
    noTransactionTitle: 'Os detalhes pessoais da transação estão ocultos',
    noTransactionText: 'Entre somente quando precisar que o assistente acesse suas informações bancárias pessoais.',
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
      <select value={language} onChange={(e) => onChange(e.target.value)} aria-label="Language">
        <option value="en">EN — English</option>
        <option value="es">ES — Español</option>
        <option value="pt">PT — Português</option>
      </select>
      <ChevronDown size={15} className="select-chevron" />
    </div>
  )
}

function LoginModal({ t, onClose, onLogin }) {
  const [username, setUsername] = useState(DEMO_USER.username)
  const [password, setPassword] = useState(DEMO_USER.password)
  const [error, setError] = useState('')

  function submit(event) {
    event.preventDefault()
    if (username === DEMO_USER.username && password === DEMO_USER.password) {
      setError('')
      onLogin()
      return
    }
    setError(t.invalid)
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
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
          </label>
          <label>
            {t.password}
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          {error && <div className="login-error">{error}</div>}
          <div className="login-actions">
            <button type="button" className="secondary" onClick={onClose}>{t.cancel}</button>
            <button type="submit" className="primary"><LogIn size={19} />{t.continueSignIn}</button>
          </div>
        </form>

        <div className="login-hint">
          <strong>{t.loginHint}</strong>
          <span>{DEMO_USER.username} / {DEMO_USER.password}</span>
        </div>
      </div>
    </div>
  )
}

function Sidebar({ t, activeSection, onSection }) {
  const items = [
    { id: 'disputes', label: t.disputes, icon: <MessageCircle size={25} /> },
    { id: 'transactions', label: t.transactions, icon: <CreditCard size={25} /> },
    { id: 'case-status', label: t.caseStatus, icon: <Clock3 size={25} /> },
  ]

  return (
    <aside className="sidebar">
      <Brand />
      <nav className="nav-list">
        {items.map((item) => (
          <button key={item.id} className={`nav-item ${activeSection === item.id ? 'active' : ''}`} onClick={() => onSection(item.id)}>
            {item.icon}{item.label}
          </button>
        ))}
      </nav>
      <div className="sidebar-divider" />
      <button className={`settings-item ${activeSection === 'settings' ? 'active-setting' : ''}`} onClick={() => onSection('settings')}>
        <Settings size={24} />
        <div><span>{t.settings}</span><small>{t.wip}</small></div>
      </button>
    </aside>
  )
}

function Header({ t, language, onLanguage, authenticated, onLogin, onLogout }) {
  return (
    <header className="topbar">
      <div className="assistant-heading">
        <div className="assistant-icon"><Bot size={34} /></div>
        <div>
          <h1>{t.title}</h1>
          <p>{t.subtitle}</p>
        </div>
      </div>
      <div className="topbar-actions">
        <LanguageSelect language={language} onChange={onLanguage} />
        <button className="icon-button" aria-label="Notifications"><Bell size={23} /></button>
        <div className="topbar-separator" />
        <div className={`user-avatar ${authenticated ? '' : 'guest-avatar'}`}>
          {authenticated ? DEMO_USER.initials : <UserRound size={22} />}
        </div>
        <div className="signed-in">
          <span>{authenticated ? t.signedIn : t.guest}</span>
          <strong>{authenticated ? DEMO_USER.customerId : t.guestId}</strong>
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

function TransactionCard({ t }) {
  return (
    <div className="transaction-card">
      <div className="transaction-card-left">
        <div className="merchant-icon"><ShoppingBag size={27} /></div>
        <div>
          <strong>{transaction.merchant}</strong>
          <span>{transaction.category}</span>
        </div>
      </div>
      <div className="transaction-card-right">
        <strong>{transaction.amount}</strong>
        <span>{transaction.date}</span>
        <span>{transaction.time}</span>
      </div>
    </div>
  )
}

function DetailRow({ icon, label, children }) {
  return (
    <div className="detail-row">
      <div className="detail-icon">{icon}</div>
      <div className="detail-copy">
        <span>{label}</span>
        {children}
      </div>
    </div>
  )
}

function TransactionDetails({ t, authenticated, disputeValidated, onLogin }) {
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

  if (!disputeValidated) {
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
        <div>
          <span>{t.merchant}</span>
          <strong>{transaction.merchant}</strong>
          <small>{transaction.category}</small>
        </div>
      </div>
      <DetailRow icon={<WalletCards size={23} />} label={t.amount}><strong>{transaction.amount}</strong></DetailRow>
      <DetailRow icon={<CalendarDays size={23} />} label={t.date}><strong>{transaction.date}</strong><small>{transaction.time}</small></DetailRow>
      <DetailRow icon={<MapPin size={23} />} label={t.location}><strong>{transaction.location}</strong><small>{transaction.channel}</small></DetailRow>
      <DetailRow icon={<CreditCard size={23} />} label={t.card}><strong>{transaction.card}</strong></DetailRow>
    </aside>
  )
}

function Chat({ t, language, authenticated, disputeValidated, onRequireLogin, justAuthenticated, onAuthMessageShown, onDisputeValidated }) {
  const initialMessages = useMemo(() => ([
    { from: 'bot', text: t.intro, time: '10:24 AM' },
  ]), [t])
  const [messages, setMessages] = useState(initialMessages)
  const [input, setInput] = useState('')
  const [showTransaction, setShowTransaction] = useState(false)
  const [evidence_ids, setEvidenceIds] = useState([])
  const [isUploadingEvidence, setIsUploadingEvidence] = useState(false)
  const composerRef = React.useRef(null)
  const messagesRef = React.useRef(null)

  function addBot(text, transactionResult = false) {
    setMessages((items) => [...items, {
      from: 'bot',
      text,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      transaction: transactionResult,
    }])
  }

  React.useEffect(() => {
    if (justAuthenticated) {
      addBot(t.authenticated)
      onAuthMessageShown()
      window.setTimeout(() => {
        addBot(t.validated, true)
        setShowTransaction(true)
        onDisputeValidated()
      }, 650)
    }
  }, [justAuthenticated])


  React.useEffect(() => {
    const container = messagesRef.current
    if (!container) return
    container.scrollTop = container.scrollHeight
  }, [messages, showTransaction, disputeValidated])

  function looksPersonal(value) {
    const lowered = value.toLowerCase()
    const personalSignals = [
      'my ', 'mine', 'transaction', 'purchase', 'card', '$320', 'yesterday',
      'mi ', 'mía', 'transacción', 'compra', 'tarjeta', 'ayer',
      'minha', 'meu ', 'transação', 'compra', 'cartão', 'ontem',
    ]
    return personalSignals.some((signal) => lowered.includes(signal))
  }

  function resizeComposer() {
    const textarea = composerRef.current
    if (!textarea) return

    textarea.style.height = '44px'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`
    textarea.style.overflowY = textarea.scrollHeight > 140 ? 'auto' : 'hidden'
  }

  function handleInput(event) {
    setInput(event.target.value)
    window.requestAnimationFrame(resizeComposer)
  }

  function handleComposerKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form.requestSubmit()
    }
  }

  async function handleEvidenceFile(file) {
    if (!file) {
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
    if (!value) return

    const history = messages.map((message) => ({
      role: message.from === 'user' ? 'user' : 'assistant',
      content: message.text,
    }))
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    setMessages((items) => [...items, { from: 'user', text: value, time }])
    setInput('')
    window.requestAnimationFrame(() => {
      if (composerRef.current) {
        composerRef.current.style.height = '44px'
        composerRef.current.style.overflowY = 'hidden'
      }
    })

    if (!authenticated && looksPersonal(value)) {
      addBot(t.authNeeded)
      onRequireLogin()
      return
    }

    const response = await send_chat(value, language, history, evidence_ids)
    addBot(response)
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
              {(message.transaction || (showTransaction && index === messages.length - 1 && message.from === 'bot')) && authenticated && disputeValidated && (
                <>
                  <TransactionCard t={t} />
                  <div className="transaction-actions">
                    <button className="primary" onClick={() => addBot(t.hardcodedOpen)}><FileText size={20} />{t.openDispute}</button>
                    <button className="secondary" onClick={() => addBot(t.hardcodedMore)}>{t.moreDetails}</button>
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
            disabled={isUploadingEvidence}
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
          onChange={handleInput}
          onKeyDown={handleComposerKeyDown}
          placeholder={t.placeholder}
          rows={1}
          aria-label={t.placeholder}
        />
        <button type="submit" className="send-button" aria-label="Send"><Send size={22} /></button>
      </form>
    </section>
  )
}

function WorkInProgress({ t, onBack }) {
  return (
    <div className="wip-page">
      <div className="wip-card">
        <div className="wip-icon"><Wrench size={34} /></div>
        <h2>{t.wipTitle}</h2>
        <p>{t.wipText}</p>
        <button className="primary" onClick={onBack}>{t.backToDisputes}</button>
      </div>
    </div>
  )
}

function App() {
  const [language, setLanguage] = useState(() => window.sessionStorage.getItem(SESSION_KEYS.language) || 'en')
  const [authenticated, setAuthenticated] = useState(() => readSessionBoolean(SESSION_KEYS.authenticated))
  const [showLogin, setShowLogin] = useState(false)
  const [activeSection, setActiveSection] = useState('disputes')
  const [justAuthenticated, setJustAuthenticated] = useState(false)
  const [disputeValidated, setDisputeValidated] = useState(() => readSessionBoolean(SESSION_KEYS.disputeValidated))
  const [loginForDispute, setLoginForDispute] = useState(false)
  const t = copy[language]

  function changeLanguage(value) {
    window.sessionStorage.setItem(SESSION_KEYS.language, value)
    setLanguage(value)
  }

  function login() {
    window.sessionStorage.setItem(SESSION_KEYS.authenticated, 'true')
    window.sessionStorage.setItem(SESSION_KEYS.disputeValidated, 'false')
    setAuthenticated(true)
    setShowLogin(false)
    setActiveSection('disputes')
    setDisputeValidated(false)
    setJustAuthenticated(loginForDispute)
    setLoginForDispute(false)
  }

  function logout() {
    window.sessionStorage.removeItem(SESSION_KEYS.authenticated)
    window.sessionStorage.removeItem(SESSION_KEYS.disputeValidated)
    setAuthenticated(false)
    setJustAuthenticated(false)
    setDisputeValidated(false)
    setLoginForDispute(false)
  }

  function validateDispute() {
    window.sessionStorage.setItem(SESSION_KEYS.disputeValidated, 'true')
    setDisputeValidated(true)
  }

  function openLogin(forDispute = false) {
    setLoginForDispute(forDispute)
    setShowLogin(true)
  }

  return (
    <div className="app-shell">
      <Sidebar t={t} activeSection={activeSection} onSection={setActiveSection} />
      <main className="app-main">
        <Header
          t={t}
          language={language}
          onLanguage={changeLanguage}
          authenticated={authenticated}
          onLogin={() => openLogin(false)}
          onLogout={logout}
        />

        {activeSection === 'disputes' ? (
          <div className="content-grid">
            <Chat
              key={language}
              t={t}
              language={language}
              authenticated={authenticated}
              disputeValidated={disputeValidated}
              onRequireLogin={() => openLogin(true)}
              justAuthenticated={justAuthenticated}
              onAuthMessageShown={() => setJustAuthenticated(false)}
              onDisputeValidated={validateDispute}
            />
            <TransactionDetails t={t} authenticated={authenticated} disputeValidated={disputeValidated} onLogin={() => openLogin(false)} />
          </div>
        ) : (
          <WorkInProgress t={t} onBack={() => setActiveSection('disputes')} />
        )}
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