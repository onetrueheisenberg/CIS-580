

//index.js file code
const express = require('express');
const axios = require('axios');
const app = express();
const PORT = 15001;  //changeme 

app.use(express.json());

app.post('/proxy/api/generate', async (req, res) => {
  try {
    const ollamaUrl = 'http://127.0.0.1:11434/api/generate';

    console.log(`Forwarding request to: ${ollamaUrl}`);

    const response = await axios({
      method: 'POST',
      url: ollamaUrl,
      headers: { 'Content-Type': 'application/json' }, 
      data: req.body,  
      timeout: 60000,  
    });

    console.log(`Received response from Ollama: ${response.status}`);

    res.status(response.status).json(response.data);
  } catch (error) {
    console.error(`Error forwarding request: ${error.message}`);

    if (error.response) {
      res.status(error.response.status).json({
        message: error.message,
        details: error.response.data,
      });
    } else {
      res.status(500).json({ message: 'Error forwarding request', details: error.message });
    }
  }
});

// Start the proxy server
app.listen(PORT, () => {
  console.log(`Proxy server running on port ${PORT}`);
});

//start me use the following command without '//' 
//node index.js