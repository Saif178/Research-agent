import os
import streamlit as st

# Secret loading/provider selection only. Retrieval, calculations, fallback data
# and Research Trace are intentionally untouched.
from config import load_runtime_environment, provider_status, secret_fingerprint, is_streamlit_cloud, secret_sources
load_runtime_environment()

from project_paths import FINANCIALS_DIR

st.set_page_config(page_title='Financial Research — Website First', page_icon='📊', layout='wide')

def _safe_dataframe(rows):
    """Convert heterogeneous trace/dataset records into Arrow-safe columns."""
    import pandas as pd
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).copy()
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].map(lambda v: '' if v is None else str(v))
        elif str(df[col].dtype).startswith(('int', 'float', 'bool')):
            continue
        else:
            df[col] = df[col].astype(str)
    return df

st.title('Financial Research')
st.caption('Website/API-first financial research with deterministic calculations and grounded synthesis')

@st.cache_resource(show_spinner=False)
def get_engine(max_steps, _provider_cache_key):
    from core.research import ResearchEngine
    from core.web_search import TavilySearch

    resolved = load_runtime_environment()
    openai_key = resolved.get('OPENAI_API_KEY')

    # OpenAI is the preferred synthesis provider when configured. On Cloud,
    # never silently assume the user's Windows localhost Ollama is reachable.
    if openai_key:
        from llm.openai_client import OpenAIClient
        llm = OpenAIClient()
        provider = 'OpenAI'
    else:
        cloud = is_streamlit_cloud()
        explicit_ollama = bool(os.getenv('OLLAMA_BASE_URL') or os.getenv('OLLAMA_MODEL'))
        if not cloud or explicit_ollama:
            try:
                from llm.ollama_client import OllamaClient
                llm = OllamaClient()
                ok, _ = llm.health()
                if not ok:
                    raise RuntimeError('Ollama is not reachable or has no usable model.')
                provider = 'Ollama'
            except Exception:
                llm = _EvidenceOnlyLLM()
                provider = 'Evidence-only'
        else:
            llm = _EvidenceOnlyLLM()
            provider = 'Evidence-only'

    engine = ResearchEngine(llm=llm, vector=None, graph=None,
                            web_search=TavilySearch(), max_steps=max_steps)
    engine.synthesis_provider = provider
    return engine

class _EvidenceOnlyLLM:
    def complete(self, prompt, system=None):
        raise RuntimeError('No remote synthesis provider is configured/reachable. Evidence-only mode is active.')

status = provider_status()
with st.sidebar:
    st.header('System Health')
    st.success('Research source: Website / financial APIs')
    st.info('Uploaded annual reports and ChromaDB are NOT used for research.')
    st.write('**Deployment**')
    st.success('Streamlit Cloud' if status['cloud'] else 'Local / self-hosted')
    st.write('**OpenAI synthesis**')
    st.success('Configured' if status['openai'] else 'Not configured')
    st.caption(f"Secret source: {secret_sources()['OPENAI_API_KEY']}")
    st.write('**Tavily web search**')
    st.success('Configured' if status['tavily'] else 'Not configured')
    st.caption(f"Secret source: {secret_sources()['TAVILY_API_KEY']}")
    st.write('**Alpha Vantage financial API**')
    st.success('Configured' if status['alphavantage'] else 'Not configured')
    st.caption(f"Secret source: {secret_sources()['ALPHAVANTAGE_API_KEY']}")
    st.write('**Synthesis fallback**')
    if status['openai']:
        st.success('OpenAI')
    elif not status['cloud']:
        st.info('Local Ollama → evidence-only if unavailable')
    elif status['ollama_configured']:
        st.info('Configured Ollama endpoint → evidence-only if unavailable')
    else:
        st.info('Evidence-only on Cloud until OpenAI or a reachable Ollama endpoint is configured')
    st.write('**Financial dataset fallback**')
    st.success(str(FINANCIALS_DIR))

research_tab, data_tab, trace_tab = st.tabs(['Research','Financial Data','Research Trace'])
with research_tab:
    q=st.text_area('Financial research query',height=120,placeholder='Example: Compare TCS and Infosys revenue growth, operating margin and free cash flow margin from FY2021 to FY2026 and calculate the changes.')
    depth=st.slider('Maximum web research steps',3,12,6)
    if q and st.button('Run Website Research',type='primary'):
        try:
            engine=get_engine(depth, secret_fingerprint())
            with st.status('Researching websites and calculating metrics...',expanded=True) as status_box:
                plan=engine.plan(q)
                result=engine.run(q, plan, progress=lambda s,x: st.write(f'Step {s}: {x}'))
                status_box.update(label='Research complete',state='complete')
            st.session_state.report=result['report']
            st.session_state.trace=result.get('actions',[])
            st.session_state.sources=result.get('sources',[])
        except Exception as exc:
            st.error('Research failed.')
            st.exception(exc)
    if st.session_state.get('report'):
        st.subheader('Financial Research Report')
        st.markdown(st.session_state.report)
        st.download_button('Download report',st.session_state.report,'financial_research_report.md','text/markdown')

with data_tab:
    st.subheader('Financial Dataset')
    st.caption(f'Used only as a secondary fallback when website/API evidence does not establish a requested value: {FINANCIALS_DIR}')
    if st.button('Preview financial dataset'):
        from ingestion.local_financials import LocalFinancialData
        rows=LocalFinancialData().search('revenue sales profit margin cash flow',directory=str(FINANCIALS_DIR),top_k=20)
        if rows: st.dataframe(_safe_dataframe(rows), width='stretch')
        else: st.info('No matching financial dataset evidence found.')

with trace_tab:
    st.subheader("Research Trace")
    trace = st.session_state.get("trace", [])
    if not trace:
        st.info("Run a website research query to populate the trace.")
    else:
        trace_df = _safe_dataframe(trace)
        st.dataframe(trace_df, width="stretch", hide_index=True)
