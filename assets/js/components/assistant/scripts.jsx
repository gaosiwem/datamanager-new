import React from 'react';
import ReactDOM from 'react-dom';


const API_URL = '/api/assistant/query';
const INTRO_MESSAGE = 'Ask about Vulekamali budgets, spending, departments, programmes, or the portal.';


function pageContext() {
  const path = window.location.pathname;
  const year = path.match(/\/(\d{4}-\d{2})(?:\/|$)/);
  const context = {};
  if (year) context.financial_year = year[1];
  if (/\/national(?:\/|$)/.test(path)) context.sphere = 'national';
  if (/\/provincial(?:\/|$)/.test(path)) context.sphere = 'provincial';
  context.screen_path = path.slice(0, 200);
  return context;
}


function statusLabel(status) {
  const labels = {
    needs_clarification: 'More detail needed',
    data_not_found: 'Data not available',
    out_of_scope: 'Outside this assistant\'s scope',
    unsupported_vulekamali_query: 'Not supported',
    blocked_prompt_attack: 'Request blocked',
    error: 'Unable to answer right now',
  };
  return labels[status] || 'Assistant response';
}


function SourceLink({ sources }) {
  if (!sources || !sources.length) return null;
  const source = sources.find(item => item.url) || sources[0];
  const url = source.url || (
    source.financial_year
      ? `/budget-summary/${encodeURIComponent(source.financial_year)}`
      : null
  );
  if (!url) return null;
  const label = source.title || (
    source.financial_year
      ? `View ${source.financial_year} budget summary`
      : 'View source'
  );
  return <a className="Assistant-sourceLink" href={url}>View resource: {label}</a>;
}


function cleanAnswer(answer) {
  return String(answer || '')
    .replace(/\s*(?:source|sources)\s*:\s*budgetportal\.[\w]+(?:,\s*\d{4}-\d{2})?\.?/gi, '')
    .replace(/(?:\*{1,2}\s*)?amount\s*:?\s*(?:\*{1,2}\s*)?r[\d\s,.]+\.?/gi, '')
    .trim();
}


function amountFromResponse(response) {
  const values = response.data && response.data.values;
  if (!Array.isArray(values) || values.length !== 1) return null;
  const value = values.find(item => item && item.amount !== undefined);
  if (!value) return null;
  const amount = Number(String(value.amount).replace(/,/g, ''));
  return isFinite(amount) ? amount : null;
}


function compactAmount(amount) {
  const scales = [
    { value: 1000000000000, label: 'trillion' },
    { value: 1000000000, label: 'billion' },
    { value: 1000000, label: 'million' },
  ];
  const scale = scales.find(item => Math.abs(amount) >= item.value);
  if (!scale) return null;
  const rounded = (amount / scale.value).toFixed(1).replace(/\.0$/, '');
  return `About R${rounded} ${scale.label}`;
}


function exactAmount(amount) {
  return `R${amount.toLocaleString('en-ZA', { maximumFractionDigits: 2 })}`;
}


function AmountSummary({ response }) {
  const amount = amountFromResponse(response);
  if (amount === null) return null;
  const exact = exactAmount(amount);
  return (
    <div className="Assistant-amount" aria-label={`Amount: ${exact}`}>
      <strong>{exact}</strong>
      {compactAmount(amount) && <span className="Assistant-amountApproximation">{compactAmount(amount)}</span>}
    </div>
  );
}


function HistoricalAmounts({ values }) {
  if (!Array.isArray(values) || !values.every(value => value.amount !== undefined)) return null;
  return (
    <ul className="Assistant-historicalAmounts">
      {values.map((value) => {
        const hasAmount = value.amount !== null && value.amount !== undefined;
        const amount = hasAmount ? Number(String(value.amount).replace(/,/g, '')) : null;
        const label = value.label || value.financial_year;
        const detail = value.label
          ? [value.budget_phase, value.financial_year].filter(Boolean).join(' · ')
          : value.budget_phase;
        return (
          <li key={`${label}-${value.financial_year}-${value.budget_phase}`}>
            <span>
              <strong>{label}</strong>
              {detail && <em>{detail}</em>}
            </span>
            <span className="Assistant-matchAmount">
              {hasAmount ? (
                <React.Fragment>
                  <strong>{exactAmount(amount)}</strong>
                  {compactAmount(amount) && <em>{compactAmount(amount)}</em>}
                </React.Fragment>
              ) : <em>No matching audited-outcome data</em>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}


function FormattedAnswer({ answer }) {
  const match = answer.match(/^(Matching Vulekamali departments for .+?\):)\s*(.+)$/i);
  if (!match) return <p className="Assistant-answerText">{answer}</p>;

  const noteMatch = match[2].match(/\.?\s*Values are shown separately[^.]*\.?$/i);
  const entries = noteMatch ? match[2].slice(0, noteMatch.index) : match[2];
  const items = entries.split(/;\s*/);
  return (
    <div className="Assistant-matches">
      <p className="Assistant-answerText">{match[1]}</p>
      <ul>
        {items.map((item, index) => {
          const entry = item.replace(/\.$/, '');
          const parts = entry.match(/^(.+?):\s*(R[\d\s,.]+)$/);
          const amount = parts && Number(parts[2].replace(/[^\d.-]/g, ''));
          return (
            <li key={`${entry}-${index}`}>
              {parts ? (
                <span className="Assistant-matchEntry">
                  <span>{parts[1]}</span>
                  <span className="Assistant-matchAmount">
                    <strong>{exactAmount(amount)}</strong>
                    {compactAmount(amount) && <em>{compactAmount(amount)}</em>}
                  </span>
                </span>
              ) : entry}
            </li>
          );
        })}
      </ul>
    </div>
  );
}


function Answer({ response }) {
  const answer = cleanAnswer(response.answer);
  const isDepartmentMatch = /^Matching Vulekamali departments for .+?\):/i.test(answer);
  const values = response.data && response.data.values;
  // A multi-department Main-appropriation response already formats itself as
  // a department list. Only audited-outcome responses need the additional
  // historical source-year list below it.
  const hasHistoricalAmounts = Boolean(
    response.data && response.data.audited_outcome_availability
    && Array.isArray(values) && values.length > 0
  );
  const readableAnswer = hasHistoricalAmounts
    ? answer.replace(
      /the verified audited-outcome data is:.+?each amount is labelled with its actual source financial year\./i,
      'The available verified audited-outcome amounts are shown below.'
    )
    : answer;
  return (
    <article className={`Assistant-answer Assistant-answer--${response.status || 'default'}`}>
      {response.status !== 'verified' && <p className="Assistant-status">{statusLabel(response.status)}</p>}
      {readableAnswer && <FormattedAnswer answer={readableAnswer} />}
      {hasHistoricalAmounts && <HistoricalAmounts values={values} />}
      {!isDepartmentMatch && <AmountSummary response={response} />}
      <SourceLink sources={response.sources} />
    </article>
  );
}


class Assistant extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      open: false,
      question: '',
      loading: false,
      history: [],
    };
    this.abortController = null;
    this.requestSequence = 0;
    this.input = null;
    this.open = this.open.bind(this);
    this.close = this.close.bind(this);
    this.submit = this.submit.bind(this);
    this.explainCurrentScreen = this.explainCurrentScreen.bind(this);
    this.updateQuestion = this.updateQuestion.bind(this);
    this.handleQuestionKeyDown = this.handleQuestionKeyDown.bind(this);
  }

  componentWillUnmount() {
    if (this.abortController) this.abortController.abort();
  }

  open() {
    this.setState({ open: true }, () => {
      if (this.input) this.input.focus();
    });
  }

  close() {
    if (this.abortController) this.abortController.abort();
    this.requestSequence += 1;
    this.setState({ open: false, loading: false });
  }

  updateQuestion(event) {
    if (this.abortController) this.abortController.abort();
    this.requestSequence += 1;
    this.setState({
      question: event.target.value,
      loading: false,
    });
  }

  handleQuestionKeyDown(event) {
    // Textareas insert a newline on Enter by default. Submit instead, while
    // retaining Shift+Enter for a deliberate multi-line question.
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    if (!this.state.loading && this.state.question.trim()) this.submit();
  }

  explainCurrentScreen() {
    this.submit(null, 'Explain this page');
  }

  async submit(event, requestedQuestion) {
    if (event) event.preventDefault();
    const question = (requestedQuestion || this.state.question).trim();
    if (!question) return;

    if (window.AbortController) this.abortController = new window.AbortController();
    const requestSequence = this.requestSequence + 1;
    this.requestSequence = requestSequence;
    const abortController = this.abortController;
    this.setState((state) => ({
      question: '',
      loading: true,
      history: state.history.concat([{ question, response: null, error: null }]),
    }));

    try {
      const request = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, context: pageContext() }),
      };
      if (abortController) request.signal = abortController.signal;
      const result = await window.fetch(API_URL, request);
      const response = await result.json();
      if (!result.ok) throw new Error(response.answer || 'The assistant is temporarily unavailable.');
      if (this.requestSequence === requestSequence) {
        this.setState((state) => ({
          loading: false,
          history: state.history.map((entry, index) => (
            index === state.history.length - 1 ? Object.assign({}, entry, { response }) : entry
          )),
        }));
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
      if (this.requestSequence === requestSequence) {
        this.setState((state) => ({
          loading: false,
          history: state.history.map((entry, index) => (
            index === state.history.length - 1 ? Object.assign({}, entry, {
              error: error.message || 'The assistant is temporarily unavailable.',
            }) : entry
          )),
        }));
      }
    } finally {
      if (this.abortController === abortController) this.abortController = null;
    }
  }

  render() {
    const { open, question, loading, history } = this.state;
    return (
      <div className="Assistant">
        {open && <button className="Assistant-backdrop" type="button" aria-label="Close AI assistant" onClick={this.close} />}
        {open && (
          <section className="Assistant-panel" role="dialog" aria-modal="true" aria-labelledby="assistant-title">
            <header className="Assistant-header">
              <div>
                <p className="Assistant-eyebrow">Vulekamali</p>
                <h2 id="assistant-title">Budget assistant</h2>
              </div>
              <button className="Assistant-close" type="button" aria-label="Close AI assistant" onClick={this.close}>×</button>
            </header>
            <div className="Assistant-body" aria-live="polite">
              <p className="Assistant-intro">{INTRO_MESSAGE}</p>
              {history.map((entry, index) => (
                <div className="Assistant-message" key={`${index}-${entry.question}`}>
                  <p className="Assistant-questionLabel">You</p>
                  <p className="Assistant-questionText">{entry.question}</p>
                  {entry.error && <p className="Assistant-error" role="alert">{entry.error}</p>}
                  {entry.response && <Answer response={entry.response} />}
                </div>
              ))}
              {loading && <p className="Assistant-loading">Finding verified information…</p>}
            </div>
            <form className="Assistant-form" onSubmit={this.submit}>
              <label className="u-sReadOnly" htmlFor="assistant-question">Your question</label>
              <textarea
                id="assistant-question"
                ref={(node) => { this.input = node; }}
                value={question}
                maxLength="2000"
                placeholder="For example, how much was allocated to Health in 2024-25?"
                onChange={this.updateQuestion}
                onKeyDown={this.handleQuestionKeyDown}
                rows="3"
              />
              <button className="Assistant-explainScreen" type="button" disabled={loading} onClick={this.explainCurrentScreen}>Explain this page</button>
              <button type="submit" disabled={loading || !question.trim()}>{loading ? 'Searching…' : 'Ask assistant'}</button>
            </form>
          </section>
        )}
        <button className="Assistant-launcher" type="button" aria-haspopup="dialog" aria-expanded={open} onClick={this.open}>
          <span aria-hidden="true">?</span> Ask the budget assistant
        </button>
      </div>
    );
  }
}


function initialise() {
  const node = document.getElementById('js-initAssistant');
  if (node) ReactDOM.render(<Assistant />, node);
}


initialise();
