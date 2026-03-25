const overviewEl = document.getElementById("overview");
const examplesEl = document.getElementById("examples");
const timelineEl = document.getElementById("timeline");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const statusText = document.getElementById("statusText");
const healthText = document.getElementById("healthText");
const template = document.getElementById("messageTemplate");

function setStatus(text) {
  statusText.textContent = text;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function appendMessage(role, html) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.classList.add(role);
  node.querySelector(".role").textContent = role === "user" ? "用户" : "助手";
  node.querySelector(".bubble").innerHTML = html;
  timelineEl.appendChild(node);
  timelineEl.scrollTop = timelineEl.scrollHeight;
}

function renderOverview(data) {
  const overview = data.overview;
  const cards = [
    ["数据库状态", overview.database_ready ? "已就绪" : "未就绪"],
    ["图表数量", overview.chart_count],
    ["知识库索引", overview.knowledge_ready ? "已生成" : "未生成"],
    ["结果2", overview.result_2_exists ? "已生成" : "未生成"],
    ["结果3", overview.result_3_exists ? "已生成" : "未生成"],
    ["年份范围", overview.years.length ? `${overview.years[0]} - ${overview.years.at(-1)}` : "暂无"],
  ];

  overviewEl.innerHTML = cards
    .map(([label, value]) => `
      <article class="metric-card">
        <p class="metric-label">${escapeHtml(label)}</p>
        <p class="metric-value">${escapeHtml(value)}</p>
      </article>
    `)
    .join("");

  examplesEl.innerHTML = data.examples
    .map((item) => `<button class="chip-btn" type="button">${escapeHtml(item)}</button>`)
    .join("");

  examplesEl.querySelectorAll(".chip-btn").forEach((button) => {
    button.addEventListener("click", () => {
      messageInput.value = button.textContent;
      messageInput.focus();
    });
  });
}

function renderResponse(payload) {
  const blocks = [`<p>${escapeHtml(payload.content || "")}</p>`];

  if (payload.sql?.length) {
    blocks.push(`
      <section class="card">
        <h3>执行 SQL</h3>
        <pre class="sql-box">${escapeHtml(payload.sql.join("\n\n"))}</pre>
      </section>
    `);
  }

  if (payload.images?.length) {
    blocks.push(
      payload.images
        .map(
          (src) => `
            <section class="card">
              <h3>图表结果</h3>
              <img class="result-image" src="${src}" alt="chart">
            </section>
          `
        )
        .join("")
    );
  }

  if (payload.references?.length) {
    blocks.push(`
      <section class="card">
        <h3>引用来源</h3>
        ${payload.references
          .map(
            (ref) => `
              <div class="reference">
                <div>${escapeHtml(ref.paper_path || "")}</div>
                <div>${escapeHtml(ref.paper_image || "")}</div>
                <div>${escapeHtml(ref.text || "")}</div>
              </div>
            `
          )
          .join("")}
      </section>
    `);
  }

  return blocks.join("");
}

async function refreshOverview() {
  const response = await fetch("/api/overview");
  const data = await response.json();
  renderOverview(data);
}

async function sendMessage(message) {
  appendMessage("user", `<p>${escapeHtml(message)}</p>`);
  appendMessage("assistant", "<p>正在处理你的问题，请稍等。</p>");
  const pendingNode = timelineEl.lastElementChild;
  setStatus("处理中");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    const payload = await response.json();
    pendingNode.remove();
    if (!response.ok || payload.ok === false) {
      appendMessage("assistant", `<p>${escapeHtml(payload.message || "请求失败")}</p>`);
      setStatus("请求失败");
      return;
    }
    appendMessage("assistant", renderResponse(payload));
    setStatus("完成");
  } catch (error) {
    pendingNode.remove();
    appendMessage("assistant", `<p>${escapeHtml(error.message || error)}</p>`);
    setStatus("请求失败");
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) {
    return;
  }
  messageInput.value = "";
  await sendMessage(message);
});

document.getElementById("refreshBtn").addEventListener("click", async () => {
  setStatus("刷新中");
  await refreshOverview();
  setStatus("就绪");
});

document.getElementById("resetSessionBtn").addEventListener("click", async () => {
  await fetch("/api/reset-session", { method: "POST" });
  appendMessage("assistant", "<p>会话上下文已清空。</p>");
});

document.getElementById("rebuildDbBtn").addEventListener("click", async () => {
  setStatus("重建数据库中");
  appendMessage("assistant", "<p>开始重建数据库，请稍等。</p>");
  const response = await fetch("/api/rebuild-db", { method: "POST" });
  const payload = await response.json();
  if (response.ok && payload.ok) {
    appendMessage("assistant", "<p>数据库重建完成。</p>");
    await refreshOverview();
    setStatus("就绪");
  } else {
    appendMessage("assistant", `<p>${escapeHtml(payload.message || "数据库重建失败")}</p>`);
    setStatus("失败");
  }
});

document.getElementById("rebuildKnowledgeBtn").addEventListener("click", async () => {
  setStatus("重建知识库中");
  appendMessage("assistant", "<p>开始重建知识库，请稍等。</p>");
  const response = await fetch("/api/rebuild-knowledge", { method: "POST" });
  const payload = await response.json();
  if (response.ok && payload.ok) {
    appendMessage("assistant", "<p>知识库重建完成。</p>");
    await refreshOverview();
    setStatus("就绪");
  } else {
    appendMessage("assistant", "<p>知识库重建失败。</p>");
    setStatus("失败");
  }
});

window.addEventListener("DOMContentLoaded", async () => {
  try {
    await fetch("/api/health");
    healthText.textContent = "服务在线";
    await refreshOverview();
  } catch (error) {
    healthText.textContent = `服务异常: ${error.message || error}`;
  }
});
