const refInput = document.getElementById("reference");
const sourceInput = document.getElementById("source");
const timeoutInput = document.getElementById("timeout");
const output = document.getElementById("output");
const statusEl = document.getElementById("status");
const metaEl = document.getElementById("meta");
const convertBtn = document.getElementById("convertBtn");
const clearBtn = document.getElementById("clearBtn");
const copyBtn = document.getElementById("copyBtn");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#9f1239" : "#67574e";
}

async function convert() {
  const reference = refInput.value.trim();
  const source = sourceInput.value;
  const timeout = Number(timeoutInput.value) || 15;

  if (!reference) {
    setStatus("请先输入 reference 文本。", true);
    return;
  }

  convertBtn.disabled = true;
  setStatus("检索中，请稍候...");
  metaEl.textContent = "";

  try {
    const resp = await fetch("/api/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reference, source, timeout })
    });

    const payload = await resp.json();
    if (!resp.ok || !payload.ok) {
      throw new Error(payload.error || "请求失败");
    }

    output.textContent = payload.bibtex;
    metaEl.textContent = `标题: ${payload.matched_title} | 来源: ${payload.source}`;
    setStatus("完成。");
  } catch (error) {
    output.textContent = "";
    metaEl.textContent = "";
    setStatus(`失败: ${error.message}`, true);
  } finally {
    convertBtn.disabled = false;
  }
}

convertBtn.addEventListener("click", convert);

clearBtn.addEventListener("click", () => {
  refInput.value = "";
  output.textContent = "";
  metaEl.textContent = "";
  setStatus("");
});

copyBtn.addEventListener("click", async () => {
  const text = output.textContent.trim();
  if (!text) {
    setStatus("没有可复制的 BibTeX。", true);
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    setStatus("BibTeX 已复制到剪贴板。");
  } catch {
    setStatus("复制失败，请手动复制。", true);
  }
});

refInput.value =
  '[12] Pan, Xudong, Mi Zhang, Yifan Yan, Shengyao Zhang, and Min Yang. "Matryoshka: Exploiting the over-parametrization of deep learning models for covert data transmission." IEEE Transactions on Pattern Analysis and Machine Intelligence 47, no. 2 (2024): 663-678.';
