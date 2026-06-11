
const SYSTEM_PROMPT = `You are the PepsTracker Peptide Advisor — a friendly assistant for pepstracker.com, tracking 17 research peptide vendors across 71+ compounds.

YOUR JOB: Help users find the right compound for their research, explain what compounds are studied for, and route them to live price comparisons. Be concise — 2-4 short paragraphs max.

FORMATTING: When recommending a compound, ALWAYS include a link like:
[Compare COMPOUND_NAME prices](/?peptide=COMPOUND_NAME)
Use the exact compound name. This renders as a clickable button.

VENDORS + codes:
- Ascension Peptides: pepstracker = 50% off (biggest discount)
- Ion Peptides: Glowlab = 15% off (best for BPC-157, SS-31, nootropics)
- Labsourced + Inno Amino + NuraPeptide: 15% off
- Fusion Peptide: pepstracker = 15% + BOGO (50+ compounds)
- AtomiK Labz: pepstracker15 = 15% off (60+ compounds)
- Glacier + Mile High + EZ + AMP: 10% off
- LA Peptides: PEPSTRACKER = 10% off (bioregulator specialist)
- Reta One: cheapest Sema base $2.90/mg
- Puratek: no code, cheapest Tirz $1.50/mg
- Apollo, Solas, GLP-1 Research Lab: affiliate links

KEY COMPOUNDS:
GLP-1/Metabolic: Semaglutide, Tirzepatide, Retatrutide, Cagrilintide
Healing: BPC-157, TB-500, BPC-157 + TB-500 Blend, GHK-Cu, SS-31
Longevity: NAD+, MOTS-c, Epithalon, Thymosin Alpha-1
Growth Hormone: Ipamorelin, CJC-1295 (with DAC), CJC-1295 (No DAC), Sermorelin, Tesamorelin, CJC/Ipa Blend, GHRP-2, GHRP-6, IGF-1 LR3
Brain/Cognitive: Semax, Selank, N-Acetyl Semax, N-Acetyl Selank, DSIP, Dihexa, PE-22-28
Tanning: Melanotan II, Melanotan I, PT-141 (Bremelanotide)
Fat Loss: AOD-9604, Lipo-C
Immune: KPV, LL-37, ARA-290
Blends: Klow Blend (80mg), Glow Blend (70mg), Tesamorelin/Ipamorelin Blend
Other: 5-Amino-1MQ, Glutathione, Methylene Blue, VIP, Pinealon, SLU-PP-332, Adamax, FOXO4-DRI, Snap-8, Vitamin B12

Always note once: products are for research purposes only, not for human consumption.`;

exports.handler = async (event) => {
  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
  };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 200, headers: cors, body: '' };
  if (event.httpMethod !== 'POST') return { statusCode: 405, body: 'Method not allowed' };

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return { statusCode: 500, body: JSON.stringify({ error: 'API key not configured' }) };

  let messages;
  try { ({ messages } = JSON.parse(event.body)); }
  catch { return { statusCode: 400, body: JSON.stringify({ error: 'Invalid body' }) }; }

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-api-key': apiKey, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({ model: 'claude-sonnet-4-20250514', max_tokens: 1000, system: SYSTEM_PROMPT, messages }),
    });
    const data = await res.json();
    return { statusCode: 200, headers: { ...cors, 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: data.content?.[0]?.text || '' }) };
  } catch (err) {
    return { statusCode: 500, headers: cors, body: JSON.stringify({ error: err.message }) };
  }
};
