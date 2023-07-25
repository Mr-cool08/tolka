from waitress import serve
import website
serve(website.app, host='0.0.0.0', port=8080)