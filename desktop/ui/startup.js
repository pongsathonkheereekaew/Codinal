const status = document.querySelector("#status");

async function connect(attemptsRemaining = 25) {
  try {
    const response = await fetch(`${window.__CODINAL_HTTP__}/v1/health`, {
      headers: {
        Authorization: `Bearer ${window.__CODINAL_TOKEN__}`,
      },
    });
    if (!response.ok) {
      throw new Error(`Runtime returned HTTP ${response.status}`);
    }
    status.textContent = "Secure local runtime connected.";
  } catch (error) {
    if (attemptsRemaining <= 1) {
      throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
    return connect(attemptsRemaining - 1);
  }
}

connect().catch((error) => {
  status.textContent = `Runtime unavailable: ${error.message}`;
});
