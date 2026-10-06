import React, { useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  CalendarDays,
  ChevronDown,
  CreditCard,
  Globe2,
  LockKeyhole,
  LogIn,
  LogOut,
  MapPin,
  MessageCircle,
  Send,
  ShoppingBag,
  UserRound,
  WalletCards,
} from 'lucide-react'
import './styles.css'
import hermesLogo from './assets/hermes-logo.svg'
import hermesIcon from './assets/hermes-icon.svg'
import {
  create_dispute,
  get_welcome_message,
  list_transactions,
  send_chat,
  send_satisfaction_feedback,
} from '../api'
import {
  get_current_username,
  has_auth_session,
  sign_in,
  sign_out,
} from '../auth'

const language_storage_key = 'factored_language'
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
  'desconozco este cargo',
  'desconozco esta transacción',
  'desconozco esta transaccion',
  'este cargo no es mío',
  'este cargo no es mio',
  'quiero reportar este cargo',
  'quiero escalar con un humano',
  'quiero hablar con un humano',
  'quiero hablar con una persona',
  'quiero un representante',
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

const transaction_history_signals = [
  'my transaction',
  'my transactions',
  'show my transactions',
  'show transactions',
  'give me my transactions',
  'give me transactions',
  'mis transaccion',
  'mis transacciones',
  'mostrar mis transacciones',
  'dame mis transacciones',
  'minha transacao',
  'minhas transacoes',
  'mostrar minhas transacoes',
  'me mostre minhas transacoes',
]

const dispute_history_signals = [
  'my dispute',
  'my disputes',
  'show my disputes',
  'show disputes',
  'give me my disputes',
  'give me disputes',
  'mis disputa',
  'mis disputas',
  'mostrar mis disputas',
  'dame mis disputas',
  'minha disputa',
  'minhas disputas',
  'minha contestacao',
  'minhas contestacoes',
  'mostrar minhas disputas',
  'mostrar minhas contestacoes',
  'me mostre minhas disputas',
]

const transaction_history_standalone = new Set([
  'transaction',
  'transactions',
  'transaccion',
  'transacciones',
  'transacao',
  'transacoes',
])

const dispute_history_standalone = new Set([
  'dispute',
  'disputes',
  'complaint',
  'complaints',
  'disputa',
  'disputas',
  'reclamo',
  'reclamos',
  'contestacao',
  'contestacoes',
])

const copy = {
  en: {
    title: 'Hermes',
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
    selectedTransactionLead: "You've selected",
    confirmSelectedTransaction: 'Would you like to start a dispute for this transaction?',
    disputeSelected: 'Start a dispute',
    chooseAnother: 'Choose another',
    disputeReasonQuestion: 'What is the reason for the dispute?',
    unrecognizedCharge: "I don't recognize this charge",
    wrongAmount: 'Wrong amount',
    chargedTwice: 'Charged twice',
    atmCashIssue: 'ATM / cash issue',
    otherReason: 'Other',
    unrecognizedDisputeReason: 'Customer does not recognize the selected charge.',
    wrongAmountDisputeReason: 'Customer reports that the transaction amount is incorrect.',
    chargedTwiceDisputeReason: 'Customer reports a duplicate charge.',
    atmCashDisputeReason: 'Customer reports an ATM or cash withdrawal issue.',
    otherDisputeReason: 'Customer reports another issue with the selected transaction.',
    escalationContinueMessage: 'You can continue chatting while your case is under human review.',
    customerContextLabel: 'Customer',
    chooseAnotherTransaction: 'Select another transaction from the list.',
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
    caseHistoryTitle: 'My disputes and complaints',
    caseDetailsTitle: 'Case details',
    summary: 'Summary',
    transactionHistoryTitle: 'My transactions',
    transactionSelectionHelp: "Select the transaction you'd like to delve into.",
    transactionsShown: 'Here are your available transactions.',
    disputesShown: 'Here are your disputes and complaints.',
    accountHistoryShown: 'Here are your available transactions and your disputes.',
    noHistory: 'No records found.',
    status: 'Status',
    caseId: 'Case ID',
    landingEyebrow: 'THE CODE OF DUTY · FACTORED AI & DATA HACKATHON',
    landingLine1: 'Every message arrives.',
    landingLine2: 'No secret crosses.',
    landingBody: 'AI-assisted transaction dispute support with grounded answers, controlled automation, and human review when needed.',
    enterHermes: 'Enter Hermes',
    landingSecurity: 'Private by design',
    landingGrounding: 'Grounded in verified records',
    landingHandoff: 'Human review when needed',
    landingMyth: 'In Greek myth, Hermes carried messages between worlds. This Hermes carries verified intent between a bank and its customers.',
    handoffTitle: 'Human review handoff',
    verifiedFacts: 'Verified facts',
    actionsTaken: 'Actions taken',
    unresolvedQuestions: 'Unresolved questions',
    linkedTransaction: 'Linked transaction',
    disputeDetailsTitle: 'Dispute details',
    source: 'Source',
    caseType: 'Case type',
    subcategory: 'Subcategory',
    resolution: 'Resolution',
    priority: 'Priority',
    affectedProduct: 'Affected product',
    transactionId: 'Transaction ID',
    linkType: 'Transaction link',
    escalationProbability: 'Escalation probability',
    humanReview: 'Human review required',
    customerIdLabel: 'Customer ID',
    processDate: 'Process date',
    receptionChannel: 'Reception channel',
    relatedBranch: 'Related branch',
    originInteraction: 'Origin interaction',
    assignedAgent: 'Assigned agent',
    assignmentDate: 'Assignment date',
    firstResponseDate: 'First response date',
    resolutionDate: 'Resolution date',
    closingDate: 'Closing date',
    slaBreached: 'SLA breached',
    resolutionDays: 'Resolution days',
    compensationGranted: 'Compensation granted',
    resolutionSatisfaction: 'Resolution satisfaction',
    repeatComplainer: 'Repeat complainer',
    updatedAt: 'Updated at',
    transactionDate: 'Transaction date',
    transactionProcessDate: 'Transaction process date',
    transactionType: 'Transaction type',
    transactionCategory: 'Transaction category',
    transactionAmount: 'Transaction amount',
    transactionCurrency: 'Transaction currency',
    amountUsd: 'Amount USD',
    transactionChannel: 'Transaction channel',
    branchId: 'Branch ID',
    merchantCategory: 'Merchant category',
    transactionCountry: 'Transaction country',
    transactionCity: 'Transaction city',
    transactionStatus: 'Transaction status',
    responseCode: 'Response code',
    isFraud: 'Fraud flag',
    fraudScore: 'Fraud score',
    latitude: 'Latitude',
    longitude: 'Longitude',
    notAvailable: 'Not available',
  },
  es: {
    title: 'Hermes',
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
    selectedTransactionLead: 'Seleccionaste',
    confirmSelectedTransaction: '¿Quieres iniciar una disputa por esta transacción?',
    disputeSelected: 'Iniciar disputa',
    chooseAnother: 'Elegir otra',
    disputeReasonQuestion: '¿Cuál es el motivo de la disputa?',
    unrecognizedCharge: 'No reconozco este cargo',
    wrongAmount: 'Monto incorrecto',
    chargedTwice: 'Cobro duplicado',
    atmCashIssue: 'Problema de ATM / efectivo',
    otherReason: 'Otro',
    unrecognizedDisputeReason: 'El cliente no reconoce el cargo seleccionado.',
    wrongAmountDisputeReason: 'El cliente reporta que el monto de la transacción es incorrecto.',
    chargedTwiceDisputeReason: 'El cliente reporta un cobro duplicado.',
    atmCashDisputeReason: 'El cliente reporta un problema con ATM o retiro de efectivo.',
    otherDisputeReason: 'El cliente reporta otro problema con la transacción seleccionada.',
    escalationContinueMessage: 'Puedes seguir escribiendo mientras tu caso está bajo revisión humana.',
    customerContextLabel: 'Cliente',
    chooseAnotherTransaction: 'Selecciona otra transacción de la lista.',
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
    caseHistoryTitle: 'Mis disputas y reclamos',
    caseDetailsTitle: 'Detalles del caso',
    summary: 'Resumen',
    transactionHistoryTitle: 'Mis transacciones',
    transactionSelectionHelp: 'Selecciona la transacción que quieres revisar en detalle.',
    transactionsShown: 'Estas son tus transacciones disponibles.',
    disputesShown: 'Estas son tus disputas y reclamos.',
    accountHistoryShown: 'Estas son tus transacciones disponibles y tus disputas.',
    noHistory: 'No se encontraron registros.',
    status: 'Estado',
    caseId: 'ID del caso',
    landingEyebrow: 'THE CODE OF DUTY · FACTORED AI & DATA HACKATHON',
    landingLine1: 'Cada mensaje llega.',
    landingLine2: 'Ningún secreto cruza.',
    landingBody: 'Asistencia con disputas de transacciones mediante respuestas fundamentadas, automatización controlada y revisión humana cuando se necesita.',
    enterHermes: 'Entrar a Hermes',
    landingSecurity: 'Privacidad por diseño',
    landingGrounding: 'Basado en registros verificados',
    landingHandoff: 'Revisión humana cuando se necesita',
    landingMyth: 'En la mitología griega, Hermes llevaba mensajes entre mundos. Este Hermes lleva intención verificada entre un banco y sus clientes.',
    handoffTitle: 'Transferencia para revisión humana',
    verifiedFacts: 'Hechos verificados',
    actionsTaken: 'Acciones realizadas',
    unresolvedQuestions: 'Preguntas pendientes',
    linkedTransaction: 'Transacción vinculada',
    disputeDetailsTitle: 'Detalles de la disputa',
    source: 'Origen',
    caseType: 'Tipo de caso',
    subcategory: 'Subcategoría',
    resolution: 'Resolución',
    priority: 'Prioridad',
    affectedProduct: 'Producto afectado',
    transactionId: 'ID de transacción',
    linkType: 'Vínculo de transacción',
    escalationProbability: 'Probabilidad de escalamiento',
    humanReview: 'Revisión humana requerida',
    customerIdLabel: 'ID de cliente',
    processDate: 'Fecha de proceso',
    receptionChannel: 'Canal de recepción',
    relatedBranch: 'Sucursal relacionada',
    originInteraction: 'Interacción de origen',
    assignedAgent: 'Agente asignado',
    assignmentDate: 'Fecha de asignación',
    firstResponseDate: 'Fecha de primera respuesta',
    resolutionDate: 'Fecha de resolución',
    closingDate: 'Fecha de cierre',
    slaBreached: 'SLA incumplido',
    resolutionDays: 'Días de resolución',
    compensationGranted: 'Compensación otorgada',
    resolutionSatisfaction: 'Satisfacción con resolución',
    repeatComplainer: 'Reclamante recurrente',
    updatedAt: 'Actualizado',
    transactionDate: 'Fecha de transacción',
    transactionProcessDate: 'Fecha de proceso de transacción',
    transactionType: 'Tipo de transacción',
    transactionCategory: 'Categoría de transacción',
    transactionAmount: 'Monto de transacción',
    transactionCurrency: 'Moneda de transacción',
    amountUsd: 'Monto USD',
    transactionChannel: 'Canal de transacción',
    branchId: 'ID de sucursal',
    merchantCategory: 'Categoría del comercio',
    transactionCountry: 'País de transacción',
    transactionCity: 'Ciudad de transacción',
    transactionStatus: 'Estado de transacción',
    responseCode: 'Código de respuesta',
    isFraud: 'Indicador de fraude',
    fraudScore: 'Puntuación de fraude',
    latitude: 'Latitud',
    longitude: 'Longitud',
    notAvailable: 'No disponible',
  },
  pt: {
    title: 'Hermes',
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
    selectedTransactionLead: 'Você selecionou',
    confirmSelectedTransaction: 'Deseja iniciar uma contestação para esta transação?',
    disputeSelected: 'Iniciar contestação',
    chooseAnother: 'Escolher outra',
    disputeReasonQuestion: 'Qual é o motivo da contestação?',
    unrecognizedCharge: 'Não reconheço esta cobrança',
    wrongAmount: 'Valor incorreto',
    chargedTwice: 'Cobrança duplicada',
    atmCashIssue: 'Problema de ATM / dinheiro',
    otherReason: 'Outro',
    unrecognizedDisputeReason: 'O cliente não reconhece a cobrança selecionada.',
    wrongAmountDisputeReason: 'O cliente informa que o valor da transação está incorreto.',
    chargedTwiceDisputeReason: 'O cliente informa uma cobrança duplicada.',
    atmCashDisputeReason: 'O cliente informa um problema com ATM ou saque em dinheiro.',
    otherDisputeReason: 'O cliente informa outro problema com a transação selecionada.',
    escalationContinueMessage: 'Você pode continuar escrevendo enquanto o caso está em análise humana.',
    customerContextLabel: 'Cliente',
    chooseAnotherTransaction: 'Selecione outra transação da lista.',
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
    caseHistoryTitle: 'Minhas contestações e reclamações',
    caseDetailsTitle: 'Detalhes do caso',
    summary: 'Resumo',
    transactionHistoryTitle: 'Minhas transações',
    transactionSelectionHelp: 'Selecione a transação que deseja analisar em detalhe.',
    transactionsShown: 'Estas são suas transações disponíveis.',
    disputesShown: 'Estas são suas contestações e reclamações.',
    accountHistoryShown: 'Estas são suas transações disponíveis e suas contestações.',
    noHistory: 'Nenhum registro encontrado.',
    status: 'Status',
    caseId: 'ID do caso',
    landingEyebrow: 'THE CODE OF DUTY · FACTORED AI & DATA HACKATHON',
    landingLine1: 'Toda mensagem chega.',
    landingLine2: 'Nenhum segredo atravessa.',
    landingBody: 'Suporte a contestações de transações com respostas fundamentadas, automação controlada e revisão humana quando necessária.',
    enterHermes: 'Entrar no Hermes',
    landingSecurity: 'Privacidade por design',
    landingGrounding: 'Baseado em registros verificados',
    landingHandoff: 'Revisão humana quando necessária',
    landingMyth: 'Na mitologia grega, Hermes levava mensagens entre mundos. Este Hermes leva intenções verificadas entre um banco e seus clientes.',
    handoffTitle: 'Transferência para revisão humana',
    verifiedFacts: 'Fatos verificados',
    actionsTaken: 'Ações realizadas',
    unresolvedQuestions: 'Questões pendentes',
    linkedTransaction: 'Transação vinculada',
    disputeDetailsTitle: 'Detalhes da contestação',
    source: 'Origem',
    caseType: 'Tipo de caso',
    subcategory: 'Subcategoria',
    resolution: 'Resolução',
    priority: 'Prioridade',
    affectedProduct: 'Produto afetado',
    transactionId: 'ID da transação',
    linkType: 'Vínculo da transação',
    escalationProbability: 'Probabilidade de escalonamento',
    humanReview: 'Revisão humana necessária',
    customerIdLabel: 'ID do cliente',
    processDate: 'Data de processamento',
    receptionChannel: 'Canal de recepção',
    relatedBranch: 'Agência relacionada',
    originInteraction: 'Interação de origem',
    assignedAgent: 'Agente atribuído',
    assignmentDate: 'Data de atribuição',
    firstResponseDate: 'Data da primeira resposta',
    resolutionDate: 'Data de resolução',
    closingDate: 'Data de encerramento',
    slaBreached: 'SLA violado',
    resolutionDays: 'Dias de resolução',
    compensationGranted: 'Compensação concedida',
    resolutionSatisfaction: 'Satisfação com a resolução',
    repeatComplainer: 'Reclamante recorrente',
    updatedAt: 'Atualizado em',
    transactionDate: 'Data da transação',
    transactionProcessDate: 'Data de processamento da transação',
    transactionType: 'Tipo de transação',
    transactionCategory: 'Categoria da transação',
    transactionAmount: 'Valor da transação',
    transactionCurrency: 'Moeda da transação',
    amountUsd: 'Valor USD',
    transactionChannel: 'Canal da transação',
    branchId: 'ID da agência',
    merchantCategory: 'Categoria do estabelecimento',
    transactionCountry: 'País da transação',
    transactionCity: 'Cidade da transação',
    transactionStatus: 'Status da transação',
    responseCode: 'Código de resposta',
    isFraud: 'Indicador de fraude',
    fraudScore: 'Pontuação de fraude',
    latitude: 'Latitude',
    longitude: 'Longitude',
    notAvailable: 'Não disponível',
  },
}

function looksPersonalDispute(value) {
  const normalized = String(value || '').toLowerCase().replace(/’/g, "'").replace(/\s+/g, ' ').trim()
  return personal_dispute_signals.some((signal) => normalized.includes(signal))
}

function normalizeAccountHistoryIntent(value) {
  return String(value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function detectAccountHistoryIntent(value) {
  const normalized = normalizeAccountHistoryIntent(value)
  const tokens = normalized.split(' ').filter(Boolean)
  const standaloneTransactions = tokens.length === 1 && transaction_history_standalone.has(normalized)
  const standaloneDisputes = tokens.length === 1 && dispute_history_standalone.has(normalized)
  const simpleBoth = [
    'transactions and disputes',
    'disputes and transactions',
    'transacciones y disputas',
    'disputas y transacciones',
    'transacoes e disputas',
    'disputas e transacoes',
    'transacoes e contestacoes',
    'contestacoes e transacoes',
  ].includes(normalized)

  const wantsTransactions = standaloneTransactions
    || simpleBoth
    || transaction_history_signals.some((signal) => normalized.includes(signal))
  const wantsDisputes = standaloneDisputes
    || simpleBoth
    || dispute_history_signals.some((signal) => normalized.includes(signal))

  if (wantsTransactions && wantsDisputes) return 'both'
  if (wantsTransactions) return 'transactions'
  if (wantsDisputes) return 'disputes'
  return null
}

function Brand() {
  return (
    <div className="brand">
      <img className="brand-logo" src={hermesLogo} alt="Hermes" />
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

function LandingPage({ t, language, onLanguage, authenticated, customerId, onLogin, onLogout, onEnter }) {
  return (
    <div className="landing-page">
      <header className="landing-header">
        <img src={hermesLogo} className="landing-wordmark" alt="Hermes" />
        <div className="landing-header-actions">
          <LanguageSelect language={language} onChange={onLanguage} />
          {authenticated ? (
            <>
              <span className="landing-user">{customerId}</span>
              <button className="landing-link" type="button" onClick={onLogout}>{t.logout}</button>
            </>
          ) : (
            <button className="landing-link" type="button" onClick={onLogin}>{t.signIn}</button>
          )}
        </div>
      </header>

      <main className="landing-hero">
        <section className="landing-copy">
          <div className="landing-eyebrow">{t.landingEyebrow}</div>
          <h1>HERMES</h1>
          <p className="landing-motto"><em>{t.landingLine1}</em><br /><em>{t.landingLine2}</em></p>
          <p className="landing-body">{t.landingBody}</p>
          <div className="landing-points">
            <span>{t.landingSecurity}</span>
            <span>{t.landingGrounding}</span>
            <span>{t.landingHandoff}</span>
          </div>
          <p className="landing-myth">{t.landingMyth}</p>
        </section>

        <section className="landing-action">
          <div className="landing-symbol" aria-label="Hermes symbol">
            <div className="landing-orbit orbit-one" />
            <div className="landing-orbit orbit-two" />
            <img src={hermesIcon} alt="" />
          </div>
          <button className="landing-enter" type="button" onClick={onEnter}>{t.enterHermes}</button>
        </section>
      </main>
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
        <div className="assistant-icon"><img src={hermesIcon} alt="" /></div>
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

function valueOrUnavailable(value, t) {
  if (value === null || value === undefined || value === '') return t.notAvailable
  return String(value)
}

function formatCaseDate(value, t) {
  if (!value) return t.notAvailable
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toLocaleString()
}

function formatCaseBoolean(value, t) {
  if (value === null || value === undefined) return t.notAvailable
  return value ? t.yes : t.no
}

function CaseField({ label, value, t }) {
  return (
    <div className="history-meta">
      <span>{label}</span>
      <b>{valueOrUnavailable(value, t)}</b>
    </div>
  )
}

function CaseDetailContent({ t, item }) {
  const probabilityValue = item?.escalation_probability == null ? null : Number(item.escalation_probability)
  const probabilityText = probabilityValue !== null && Number.isFinite(probabilityValue)
    ? `${(probabilityValue * 100).toFixed(1)}%`
    : t.notAvailable

  const claimedAmount = item?.claimed_amount == null
    ? t.notAvailable
    : `${item.currency || ''} ${item.claimed_amount}`.trim()

  const transactionAmount = item?.transaction_amount == null
    ? t.notAvailable
    : `${item.transaction_currency || ''} ${item.transaction_amount}`.trim()

  return (
    <>
      <div className="history-item-head">
        <strong>{item?.category || item?.case_type || t.notAvailable}</strong>
        <span>{item?.status || t.notAvailable}</span>
      </div>

      <CaseField label={t.caseId} value={item?.case_id} t={t} />
      <CaseField label={t.date} value={formatCaseDate(item?.case_date, t)} t={t} />
      <CaseField label={t.source} value={item?.source} t={t} />
      <CaseField label={t.customerIdLabel} value={item?.customer_id} t={t} />
      <CaseField label={t.caseType} value={item?.case_type} t={t} />
      <CaseField label={t.subcategory} value={item?.subcategory} t={t} />
      <CaseField label={t.amount} value={claimedAmount} t={t} />
      <CaseField label={t.summary} value={item?.summary} t={t} />
      <CaseField label={t.processDate} value={formatCaseDate(item?.process_date, t)} t={t} />
      <CaseField label={t.receptionChannel} value={item?.reception_channel} t={t} />
      <CaseField label={t.affectedProduct} value={item?.affected_product_id} t={t} />
      <CaseField label={t.relatedBranch} value={item?.related_branch_id} t={t} />
      <CaseField label={t.originInteraction} value={item?.origin_interaction_id} t={t} />
      <CaseField label={t.resolution} value={item?.resolution} t={t} />
      <CaseField label={t.priority} value={item?.priority} t={t} />
      <CaseField label={t.assignedAgent} value={item?.assigned_agent_id} t={t} />
      <CaseField label={t.assignmentDate} value={formatCaseDate(item?.assignment_date, t)} t={t} />
      <CaseField label={t.firstResponseDate} value={formatCaseDate(item?.first_response_date, t)} t={t} />
      <CaseField label={t.resolutionDate} value={formatCaseDate(item?.resolution_date, t)} t={t} />
      <CaseField label={t.closingDate} value={formatCaseDate(item?.closing_date, t)} t={t} />
      <CaseField label={t.slaBreached} value={formatCaseBoolean(item?.sla_breached, t)} t={t} />
      <CaseField label={t.resolutionDays} value={item?.resolution_days} t={t} />
      <CaseField label={t.compensationGranted} value={item?.compensation_granted} t={t} />
      <CaseField label={t.resolutionSatisfaction} value={item?.resolution_satisfaction} t={t} />
      <CaseField label={t.repeatComplainer} value={formatCaseBoolean(item?.is_repeat_complainer, t)} t={t} />
      <CaseField label={t.updatedAt} value={formatCaseDate(item?.updated_at, t)} t={t} />
      <CaseField label={t.transactionId} value={item?.transaction_id} t={t} />
      <CaseField label={t.linkType} value={item?.transaction_link_type} t={t} />
      <CaseField label={t.escalationProbability} value={probabilityText} t={t} />
      <CaseField label={t.humanReview} value={formatCaseBoolean(item?.requires_human_review, t)} t={t} />

      <div className="linked-transaction-block">
        <h3>{t.linkedTransaction}</h3>
        <CaseField label={t.transactionDate} value={formatCaseDate(item?.transaction_date, t)} t={t} />
        <CaseField label={t.transactionProcessDate} value={formatCaseDate(item?.transaction_process_date, t)} t={t} />
        <CaseField label={t.card} value={item?.transaction_product_id} t={t} />
        <CaseField label={t.transactionType} value={item?.transaction_type} t={t} />
        <CaseField label={t.transactionCategory} value={item?.transaction_category} t={t} />
        <CaseField label={t.transactionAmount} value={transactionAmount} t={t} />
        <CaseField label={t.amountUsd} value={item?.transaction_amount_usd} t={t} />
        <CaseField label={t.transactionChannel} value={item?.transaction_channel} t={t} />
        <CaseField label={t.branchId} value={item?.transaction_branch_id} t={t} />
        <CaseField label={t.merchant} value={item?.merchant_name} t={t} />
        <CaseField label={t.merchantCategory} value={item?.merchant_category} t={t} />
        <CaseField label={t.transactionCountry} value={item?.transaction_country} t={t} />
        <CaseField label={t.transactionCity} value={item?.transaction_city} t={t} />
        <CaseField label={t.transactionStatus} value={item?.transaction_status} t={t} />
        <CaseField label={t.responseCode} value={item?.transaction_response_code} t={t} />
        <CaseField label={t.isFraud} value={formatCaseBoolean(item?.transaction_is_fraud, t)} t={t} />
        <CaseField label={t.fraudScore} value={item?.transaction_fraud_score} t={t} />
        <CaseField label={t.latitude} value={item?.transaction_latitude} t={t} />
        <CaseField label={t.longitude} value={item?.transaction_longitude} t={t} />
      </div>
    </>
  )
}

function CaseHistoryAccordionItem({ t, item }) {
  return (
    <details className="history-item history-accordion">
      <summary className="history-accordion-summary">
        <div className="history-accordion-title">
          <strong>{item?.category || item?.case_type || t.notAvailable}</strong>
          <small>{formatCaseDate(item?.case_date, t)}</small>
        </div>
        <div className="history-accordion-status">
          <span>{item?.status || t.notAvailable}</span>
          <ChevronDown className="history-accordion-chevron" size={18} />
        </div>
      </summary>
      <div className="history-accordion-body">
        <CaseDetailContent t={t} item={item} />
      </div>
    </details>
  )
}

function CaseHistoryPanel({ t, items }) {
  return (
    <aside className="details-panel history-panel">
      <h2>{t.caseHistoryTitle}</h2>
      {!items.length && <p className="history-empty">{t.noHistory}</p>}
      <div className="history-list">
        {items.map((item) => (
          <CaseHistoryAccordionItem t={t} item={item} key={item.case_id} />
        ))}
      </div>
    </aside>
  )
}

function CaseDetailPanel({ t, item, linkedTransaction }) {
  return (
    <aside className="details-panel history-panel">
      <h2>{t.caseDetailsTitle}</h2>
      <div className="history-list">
        <div className="history-item">
          <CaseDetailContent t={t} item={item} />
        </div>
      </div>
    </aside>
  )
}

function TransactionHistoryAccordionItem({ t, item, selected, radioName, onSelect }) {
  return (
    <details className={`history-item history-accordion transaction-history-choice ${selected ? 'selected' : ''}`}>
      <summary className="history-accordion-summary transaction-accordion-summary">
        <span
          className="transaction-radio-wrap"
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          <input
            className="transaction-radio"
            type="radio"
            name={radioName}
            checked={selected}
            onChange={() => onSelect?.(item)}
            aria-label={`${t.select}: ${item.merchant || item.transaction_id || ''}`}
          />
        </span>
        <div className="history-accordion-title transaction-accordion-title">
          <strong>{item.merchant || '-'}</strong>
          <small>{[item.date, item.time].filter(Boolean).join(' ')}</small>
        </div>
        <div className="history-accordion-status transaction-accordion-amount">
          <span>{item.amount || '-'}</span>
          <ChevronDown className="history-accordion-chevron" size={18} />
        </div>
      </summary>
      <div className="history-accordion-body transaction-accordion-body">
        {item.category && <div className="history-meta"><span>{t.transactionCategory}</span><b>{item.category}</b></div>}
        {item.location && <div className="history-meta"><span>{t.location}</span><b>{item.location}</b></div>}
        {item.channel && <div className="history-meta"><span>{t.transactionChannel}</span><b>{item.channel}</b></div>}
        {item.card && <div className="history-meta"><span>{t.card}</span><b>{item.card}</b></div>}
        {item.transaction_id && <div className="history-meta"><span>{t.transactionId}</span><b>{item.transaction_id}</b></div>}
      </div>
    </details>
  )
}

function TransactionHistoryPanel({ t, items, selectable = false, selectedTransactionId = null, onSelect = null }) {
  return (
    <aside className="details-panel history-panel">
      <h2>{t.transactionHistoryTitle}</h2>
      <p className="transaction-selection-help">{t.transactionSelectionHelp}</p>
      {!items.length && <p className="history-empty">{t.noHistory}</p>}
      <div className="history-list">
        {items.map((item) => (
          <TransactionHistoryAccordionItem
            t={t}
            item={item}
            key={item.transaction_id}
            selected={selectedTransactionId === item.transaction_id}
            radioName="dispute-transaction"
            onSelect={onSelect}
          />
        ))}
      </div>
    </aside>
  )
}

function AccountHistoryPanel({ t, transactions, cases, selectedTransactionId = null, onSelectTransaction = null }) {
  return (
    <aside className="details-panel history-panel">
      <h2>{t.transactionHistoryTitle}</h2>
      <p className="transaction-selection-help">{t.transactionSelectionHelp}</p>
      {!transactions.length && <p className="history-empty">{t.noHistory}</p>}
      <div className="history-list">
        {transactions.map((item) => (
          <TransactionHistoryAccordionItem
            t={t}
            item={item}
            key={item.transaction_id}
            selected={selectedTransactionId === item.transaction_id}
            radioName="account-history-transaction"
            onSelect={onSelectTransaction}
          />
        ))}
      </div>

      <div className="linked-transaction-block">
        <h2>{t.caseHistoryTitle}</h2>
        {!cases.length && <p className="history-empty">{t.noHistory}</p>}
        <div className="history-list">
          {cases.map((item) => (
            <CaseHistoryAccordionItem t={t} item={item} key={item.case_id} />
          ))}
        </div>
      </div>
    </aside>
  )
}

function DisputeDetailPanel({ t, item, transaction }) {
  if (!item) return null

  const normalizedItem = {
    case_id: item.dispute_id,
    case_date: item.created_at,
    source: 'FACTORED_AI',
    case_type: 'Dispute',
    category: 'Transaction dispute',
    subcategory: null,
    status: item.status,
    claimed_amount: item.claimed_amount,
    currency: item.currency,
    summary: item.reason,
    resolution: null,
    priority: null,
    affected_product_id: item.product_id,
    transaction_id: item.transaction_id,
    transaction_link_type: 'EXACT_DISPUTE_LINK',
    escalation_probability: item.escalation_probability,
    requires_human_review: item.requires_human_review,
  }

  return (
    <aside className="details-panel history-panel">
      <h2>{t.disputeDetailsTitle}</h2>
      <div className="history-list">
        <div className="history-item">
          <CaseDetailContent t={t} item={normalizedItem} linkedTransaction={null} />
          {transaction && (
            <div className="linked-transaction-block">
              <h3>{t.linkedTransaction}</h3>
              <TransactionCard transaction={transaction} />
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}

function HandoffPanel({ t, handoff, dispute }) {
  const facts = handoff?.verified_facts || {}
  const actions = handoff?.actions_taken || []
  const questions = handoff?.unresolved_questions || []
  return (
    <aside className="details-panel history-panel handoff-panel">
      <div className="handoff-kicker">ESCALATED</div>
      <h2>{t.handoffTitle}</h2>
      {dispute && <div className="history-meta"><span>{t.caseId}</span><b>{dispute.dispute_id}</b></div>}

      <details className="handoff-section handoff-accordion">
        <summary><span>{t.verifiedFacts}</span><ChevronDown className="history-accordion-chevron" size={18} /></summary>
        <div className="handoff-accordion-body">
          {Object.entries(facts).filter(([, value]) => value !== null && value !== undefined && value !== '').map(([key, value]) => (
            <div className="handoff-row" key={key}><span>{key.replaceAll('_', ' ')}</span><b>{String(value)}</b></div>
          ))}
        </div>
      </details>

      <details className="handoff-section handoff-accordion">
        <summary><span>{t.actionsTaken}</span><ChevronDown className="history-accordion-chevron" size={18} /></summary>
        <div className="handoff-accordion-body"><ul>{actions.map((item) => <li key={item}>{item}</li>)}</ul></div>
      </details>

      <details className="handoff-section handoff-accordion">
        <summary><span>{t.unresolvedQuestions}</span><ChevronDown className="history-accordion-chevron" size={18} /></summary>
        <div className="handoff-accordion-body"><ul>{questions.map((item) => <li key={item}>{item}</li>)}</ul></div>
      </details>
    </aside>
  )
}

function RightPanel({ t, authenticated, transaction, panelData, onLogin, onSelectTransaction }) {
  if (authenticated && panelData?.type === 'handoff') {
    return <HandoffPanel t={t} handoff={panelData.handoff} dispute={panelData.dispute} />
  }

  if (authenticated && panelData?.type === 'dispute') {
    return <DisputeDetailPanel t={t} item={panelData.item} transaction={panelData.linkedTransaction || null} />
  }

  if (authenticated && panelData?.type === 'case_detail') {
    return <CaseDetailPanel t={t} item={panelData.item} linkedTransaction={panelData.linkedTransaction} />
  }

  if (authenticated && panelData?.type === 'transaction_selection') {
    return (
      <TransactionHistoryPanel
        t={t}
        items={panelData.items || []}
        selectable
        selectedTransactionId={transaction?.transaction_id || null}
        onSelect={onSelectTransaction}
      />
    )
  }

  if (authenticated && panelData?.type === 'overview') {
    return (
      <AccountHistoryPanel
        t={t}
        transactions={panelData.transactions || []}
        cases={panelData.cases || []}
        selectedTransactionId={transaction?.transaction_id || null}
        onSelectTransaction={onSelectTransaction}
      />
    )
  }

  if (authenticated && panelData?.type === 'transactions') {
    return (
      <TransactionHistoryPanel
        t={t}
        items={panelData.items || []}
        selectable
        selectedTransactionId={transaction?.transaction_id || null}
        onSelect={onSelectTransaction}
      />
    )
  }

  if (transaction) {
    return <TransactionDetails t={t} authenticated={authenticated} transaction={transaction} onLogin={onLogin} />
  }

  if (authenticated && panelData?.type === 'cases') {
    return <CaseHistoryPanel t={t} items={panelData.items || []} />
  }

  return <TransactionDetails t={t} authenticated={authenticated} transaction={null} onLogin={onLogin} />
}

function Chat({ t, language, authenticated, customerId, transaction, onTransaction, onRightPanelData, onRequireLogin }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [interactionId] = useState(() => crypto.randomUUID())
  const [interactionFinished, setInteractionFinished] = useState(false)
  const [awaitingFeedback, setAwaitingFeedback] = useState(false)
  const [pendingDisputeReason, setPendingDisputeReason] = useState('')
  const [pendingLoginRequest, setPendingLoginRequest] = useState(null)
  const [transactions, setTransactions] = useState([])
  const [transactionsError, setTransactionsError] = useState('')
  const [showTransactionSelection, setShowTransactionSelection] = useState(false)
  const [readyToOpenDispute, setReadyToOpenDispute] = useState(false)
  const [showDisputeReasons, setShowDisputeReasons] = useState(false)
  const [forceHumanReview, setForceHumanReview] = useState(false)
  const composerRef = React.useRef(null)
  const messagesRef = React.useRef(null)
  const welcomeLoadedRef = React.useRef(false)
  const selectionHandledRef = React.useRef('')

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

  function withCustomerContext(response, fallback) {
    const message = response || fallback
    if (!customerId) return message
    return `${t.customerContextLabel}: ${customerId}. ${message}`
  }

  async function loadTransactionHistory() {
    if (!authenticated) return { items: [], response: null }

    const prompts = {
      en: 'my transactions',
      es: 'mis transacciones',
      pt: 'minhas transações',
    }
    const result = await send_chat(
      prompts[language] || prompts.en,
      language,
      [],
      interactionId,
    )
    const formatted = (result.transaction_history || []).map(formatTransaction).filter(Boolean)
    setTransactions(formatted)
    setTransactionsError('')
    return {
      items: formatted,
      response: result.response || null,
    }
  }

  async function loadDisputes() {
    if (!authenticated) return { items: [], response: null }

    const prompts = {
      en: 'my disputes',
      es: 'mis disputas',
      pt: 'minhas contestações',
    }
    const result = await send_chat(
      prompts[language] || prompts.en,
      language,
      [],
      interactionId,
    )
    return {
      items: Array.isArray(result.case_history) ? result.case_history : [],
      response: result.response || null,
    }
  }

  async function showAccountHistory(intent) {
    onTransaction(null)
    selectionHandledRef.current = ''
    setShowTransactionSelection(false)
    setReadyToOpenDispute(false)
    setShowDisputeReasons(false)

    if (intent === 'transactions') {
      const history = await loadTransactionHistory()
      onRightPanelData({ type: 'transactions', items: history.items })
      addBot(withCustomerContext(history.response, t.transactionsShown))
      return
    }

    if (intent === 'disputes') {
      const history = await loadDisputes()
      onRightPanelData({ type: 'cases', items: history.items })
      addBot(withCustomerContext(history.response, t.disputesShown))
      return
    }

    const [transactionHistory, disputeHistory] = await Promise.all([
      loadTransactionHistory(),
      loadDisputes(),
    ])

    onRightPanelData({
      type: 'overview',
      transactions: transactionHistory.items,
      cases: disputeHistory.items,
    })
    addBot(withCustomerContext(transactionHistory.response, t.accountHistoryShown))
  }

  async function enterTransactionSelection(reason) {
    setPendingDisputeReason(reason)
    setAwaitingFeedback(false)
    setReadyToOpenDispute(false)
    setShowDisputeReasons(false)
    selectionHandledRef.current = ''
    onTransaction(null)
    onRightPanelData(null)
    const available = transactions.length ? transactions : await loadTransactions()
    setShowTransactionSelection(true)

    if (available !== null) {
      onRightPanelData({
        type: 'transaction_selection',
        items: available,
      })
    }

    if (available !== null && !available.length) {
      setTransactionsError(t.noTransactions)
    }
  }

  async function processChatMessage(message, history) {
    try {
      const accountHistoryIntent = detectAccountHistoryIntent(message)

      if (accountHistoryIntent) {
        if (!authenticated) {
          setPendingLoginRequest({ message, history })
          onRequireLogin()
          return
        }

        await showAccountHistory(accountHistoryIntent)
        return
      }

      const result = await send_chat(
        message,
        language,
        history,
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

      if (result.case_detail) {
        onTransaction(null)
        onRightPanelData({
          type: 'case_detail',
          item: result.case_detail,
          linkedTransaction: result.linked_transaction || null,
        })
        setShowTransactionSelection(false)
        setReadyToOpenDispute(false)
      }

      if (Array.isArray(result.case_history)) {
        onTransaction(null)
        onRightPanelData({
          type: 'cases',
          items: result.case_history,
        })
        setShowTransactionSelection(false)
        setReadyToOpenDispute(false)
      }

      if (Array.isArray(result.transaction_history)) {
        onTransaction(null)
        onRightPanelData({
          type: 'transactions',
          items: result.transaction_history.map(formatTransaction).filter(Boolean),
        })
        setShowTransactionSelection(false)
        setReadyToOpenDispute(false)
      }

      if (result.needs_satisfaction_feedback) {
        setForceHumanReview(false)
        setPendingDisputeReason(message)
        setAwaitingFeedback(true)
        addBot(t.satisfactionQuestion, { feedbackPrompt: true })
        return
      }

      if (result.human_escalation_requested) {
        setForceHumanReview(true)
      }

      if (result.needs_transaction_selection) {
        if (!result.human_escalation_requested) setForceHumanReview(false)
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
      onRightPanelData(null)
    }
  }, [authenticated])

  React.useEffect(() => {
    if (!authenticated || !pendingLoginRequest) return

    const request = pendingLoginRequest
    setPendingLoginRequest(null)
    processChatMessage(request.message, request.history)
  }, [authenticated, pendingLoginRequest])

  React.useEffect(() => {
    if (!transaction || interactionFinished) return
    if (selectionHandledRef.current === transaction.transaction_id) return

    selectionHandledRef.current = transaction.transaction_id
    setShowTransactionSelection(false)
    setShowDisputeReasons(false)
    setReadyToOpenDispute(true)
  }, [transaction, interactionFinished])

  React.useEffect(() => {
    const container = messagesRef.current

    if (container) {
      container.scrollTop = container.scrollHeight
    }
  }, [messages, showTransactionSelection, readyToOpenDispute, showDisputeReasons])

  function resizeComposer() {
    const textarea = composerRef.current

    if (!textarea) return

    textarea.style.height = '44px'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`
    textarea.style.overflowY = textarea.scrollHeight > 140 ? 'auto' : 'hidden'
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
        setShowDisputeReasons(false)
        return
      }

      if (result.needs_transaction_selection) {
        setForceHumanReview(false)
        await enterTransactionSelection(pendingDisputeReason)
      }
    } catch (error) {
      showError(error)
    }
  }

  function selectTransaction(selected) {
    onTransaction(selected)
  }

  function confirmSelectedTransaction() {
    addUser(t.disputeSelected)
    setReadyToOpenDispute(false)
    setShowDisputeReasons(true)
    addBot(t.disputeReasonQuestion)
  }

  async function chooseDisputeReason(label, reason) {
    setPendingDisputeReason(reason)
    setShowDisputeReasons(false)
    addUser(label)
    await openDispute(reason)
  }

  function chooseAnotherTransaction() {
    addUser(t.chooseAnother)
    selectionHandledRef.current = ''
    onTransaction(null)
    setReadyToOpenDispute(false)
    setShowDisputeReasons(false)
    setShowTransactionSelection(true)
    onRightPanelData({
      type: 'transaction_selection',
      items: transactions,
    })
    addBot(t.chooseAnotherTransaction)
  }

  async function openDispute(reasonOverride = '') {
    if (!authenticated) {
      onRequireLogin()
      return
    }

    const disputeReason = reasonOverride || pendingDisputeReason
    if (!transaction || !disputeReason || interactionFinished) return

    try {
      const result = await create_dispute({
        transaction_id: transaction.transaction_id,
        reason: disputeReason,
        language,
        interaction_id: interactionId,
        force_human_review: forceHumanReview,
      })

      if (result.response) {
        addBot(result.response)
      } else {
        addBot(`${result.dispute.status}: ${result.dispute.dispute_id}`)
      }

      if (result.handoff) {
        onTransaction(null)
        onRightPanelData({ type: 'handoff', handoff: result.handoff, dispute: result.dispute })
        addBot(t.escalationContinueMessage)
      } else {
        const selectedTransaction = transaction
        onTransaction(null)
        onRightPanelData({
          type: 'dispute',
          item: result.dispute,
          linkedTransaction: selectedTransaction,
        })
      }

      setInteractionFinished(Boolean(result.interaction_finished))
      setReadyToOpenDispute(false)
      setShowDisputeReasons(false)
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
            {message.from === 'bot' && <div className="bot-avatar"><img src={hermesIcon} alt="" /></div>}
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
          <div className="transaction-selection transaction-selection-prompt">
            <div className="message-bubble bot">{t.selectTransaction}</div>
            {transactionsError && <div className="selection-error">{transactionsError}</div>}
          </div>
        )}

        {readyToOpenDispute && transaction && !interactionFinished && (
          <div className="message-row bot selection-confirmation-row">
            <div className="bot-avatar"><img src={hermesIcon} alt="" /></div>
            <div className="message-stack selection-confirmation-stack">
              <div className="message-bubble bot selection-confirmation-bubble">
                <span>{t.selectedTransactionLead}:</span>
                <strong>{transaction.merchant}</strong>
                <span>{[transaction.amount, transaction.date, transaction.time].filter(Boolean).join(' · ')}</span>
                <span>{t.confirmSelectedTransaction}</span>
              </div>
              <div className="feedback-actions selection-confirmation-actions">
                <button className="primary" type="button" onClick={confirmSelectedTransaction}>{t.disputeSelected}</button>
                <button className="secondary" type="button" onClick={chooseAnotherTransaction}>{t.chooseAnother}</button>
              </div>
            </div>
          </div>
        )}

        {showDisputeReasons && transaction && !interactionFinished && (
          <div className="message-row bot selection-confirmation-row">
            <div className="bot-avatar"><img src={hermesIcon} alt="" /></div>
            <div className="message-stack selection-confirmation-stack">
              <div className="feedback-actions dispute-reason-actions">
                <button className="primary" type="button" onClick={() => chooseDisputeReason(t.unrecognizedCharge, t.unrecognizedDisputeReason)}>{t.unrecognizedCharge}</button>
                <button className="secondary" type="button" onClick={() => chooseDisputeReason(t.wrongAmount, t.wrongAmountDisputeReason)}>{t.wrongAmount}</button>
                <button className="secondary" type="button" onClick={() => chooseDisputeReason(t.chargedTwice, t.chargedTwiceDisputeReason)}>{t.chargedTwice}</button>
                <button className="secondary" type="button" onClick={() => chooseDisputeReason(t.atmCashIssue, t.atmCashDisputeReason)}>{t.atmCashIssue}</button>
                <button className="secondary" type="button" onClick={() => chooseDisputeReason(t.otherReason, t.otherDisputeReason)}>{t.otherReason}</button>
                <button className="secondary" type="button" onClick={chooseAnotherTransaction}>{t.chooseAnother}</button>
              </div>
            </div>
          </div>
        )}
      </div>

      <form className="composer" onSubmit={submit}>
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
  const [showWorkspace, setShowWorkspace] = useState(false)
  const [transaction, setTransaction] = useState(null)
  const [panelData, setPanelData] = useState(null)
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
    setShowWorkspace(true)
  }

  function logout() {
    sign_out()
    setAuthenticated(false)
    setCustomerId('')
    setTransaction(null)
    setPanelData(null)
    setSessionVersion((value) => value + 1)
  }

  if (!showWorkspace) {
    return (
      <>
        <LandingPage
          t={t}
          language={language}
          onLanguage={changeLanguage}
          authenticated={authenticated}
          customerId={customerId}
          onLogin={() => setShowLogin(true)}
          onLogout={logout}
          onEnter={() => setShowWorkspace(true)}
        />
        {showLogin && <LoginModal t={t} onClose={() => setShowLogin(false)} onLogin={login} />}
      </>
    )
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
            customerId={customerId}
            transaction={transaction}
            onTransaction={setTransaction}
            onRightPanelData={setPanelData}
            onRequireLogin={() => setShowLogin(true)}
          />
          <RightPanel
            t={t}
            authenticated={authenticated}
            transaction={transaction}
            panelData={panelData}
            onLogin={() => setShowLogin(true)}
            onSelectTransaction={setTransaction}
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
