import express from "express";

const app = express();
app.use(express.json());
const OLLAMA_URL = "http://46.225.170.117";

app.get("/", (req, res) => {
  res.send("VERSION 2");
});

app.post("/coach", async (req, res) => {
  const { engineData, userLevel } = req.body;

  const prompt = `
You are a chess coach.

Engine data:
${JSON.stringify(engineData)}

User level: ${userLevel}

Explain in 3 parts:
1. Mistake
2. Consequence
3. Better idea

Keep it under 100 words.
`;

  try {
    const response = await fetch(`${OLLAMA_URL}/api/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: "qwen2.5:7b-instruct-q2_K",
        prompt,
        stream: false
      })
    });

    const data = await response.json();

    res.json({
      text: data.response
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "LLM failed" });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
