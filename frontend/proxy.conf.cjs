module.exports = { '/backend/**': { target: process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000', secure: false, changeOrigin: false, pathRewrite: { '^/backend': '/api/v1' } } };
