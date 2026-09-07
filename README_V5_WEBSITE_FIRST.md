# Website-First Financial Research Mode

This version keeps the stable v4.4 application shell but changes the research path to website/API-first evidence.

## Evidence hierarchy
1. Official/company/regulatory websites and supplied financial APIs (`[W#]`).
2. Other reputable web sources (`[W#]`).
3. Local financials dataset (`[F#]`) only where explicitly wired into the application and web evidence does not establish the value.
4. If evidence is insufficient: `Not established by the retrieved evidence.`

Uploaded annual reports in ChromaDB are **not used by the website-first research path**.

## Calculations
The research layer can deterministically calculate common metrics when the required inputs are explicitly present in retrieved evidence, including revenue growth, gross margin, operating margin, FCF margin, debt/equity and CAGR. The final answer must cite the inputs and show the formula.

## Configuration
Set `TAVILY_API_KEY` for website search. Alpha Vantage is used when `ALPHAVANTAGE_API_KEY` is configured and an entity has a ticker symbol.
