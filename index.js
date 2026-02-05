// backend/index.js
const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const twilio = require('twilio');

const app = express();
app.use(cors());
app.use(bodyParser.json());

const accountSid = process.env.TWILIO_ACCOUNT_SID;
const authToken = process.env.TWILIO_AUTH_TOKEN;
const twilioPhone = process.env.TWILIO_PHONE_NUMBER;

if (!accountSid || !authToken || !twilioPhone) {
  console.warn('Twilio credentials missing. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER.');
}

const client = (accountSid && authToken) ? twilio(accountSid, authToken) : null;

// Store SMS preferences in memory (for demo)
const userPreferences = {};

// Endpoint to save SMS preferences
app.post('/sms-preferences', (req, res) => {
  const { phone, preferences } = req.body;
  if (!phone || !preferences) return res.status(400).send('Missing phone or preferences');
  userPreferences[phone] = preferences;
  res.send('Preferences saved');
});

// Endpoint to send an SMS alert
app.post('/send-sms-alert', async (req, res) => {
  const { phone, message } = req.body;
  if (!phone || !message) return res.status(400).send('Missing phone or message');
  if (!client || !twilioPhone) return res.status(503).send('SMS not configured. Set Twilio env vars.');

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
