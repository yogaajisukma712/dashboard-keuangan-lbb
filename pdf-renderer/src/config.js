module.exports = {
  port: process.env.PDF_RENDERER_PORT || 3001,
  token: process.env.PDF_RENDERER_TOKEN || '',
  chromiumPath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
};
