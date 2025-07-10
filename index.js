// backend/index.js
const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const twilio = require('twilio');

const app = express();
app.use(cors());
app.use(bodyParser.json());

const accountSid = 'YOUR_TWILIO_ACCOUNT_SID';
const authToken = 'YOUR_TWILIO_AUTH_TOKEN';
const twilioPhone = 'YOUR_TWILIO_PHONE_NUMBER';

const client = twilio(accountSid, authToken);

// Store SMS preferences in memory (for demo)
const userPreferences = {};

// Endpoint to save SMS preferences
app.post('/sms-preferences', (req, res) => {
  const { phone, preferences } = req.body;
  if (!phone || !preferences) return res.status(400).send('Missing phone or preferences');
  userPreferences[phone] = preferences;
  res.send('Preferences saved');
});

// Endpoint to send an SMS alert (simulate triggering alert)
app.post('/send-sms-alert', async (req, res) => {
  const { phone, message } = req.body;
  if (!phone || !message) return res.status(400).send('Missing phone or message');

  try {
    await client.messages.create({
      from: twilioPhone,
      to: phone,
      body: message
    });
    res.send('SMS sent');
  } catch (err) {
    console.error(err);
    res.status(500).send('Failed to send SMS');
  }
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
