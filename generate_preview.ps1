$content = Get-Content -Raw job-alert-guide.jsx
$content = $content -replace 'import .* from "react";?', 'const { useState } = React;'
$content = $content -replace 'export default function', 'function'

$html = @"
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Preview JobAlertGuide</title>
  <script src="https://unpkg.com/react@18/umd/react.development.js" crossorigin></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js" crossorigin></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body style="margin:0;">
  <div id="root"></div>
  <script type="text/babel">
$content

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<JobAlertGuide />);
  </script>
</body>
</html>
"@

Set-Content -Path preview.html -Value $html -Encoding UTF8
