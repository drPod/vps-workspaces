'use strict';
(async () => {
  const key = new URLSearchParams(location.hash.slice(1)).get('key');
  if (!key) {
    document.querySelector('h1').textContent = 'Use your sharing link';
    document.querySelector('#message').textContent = 'Open the complete link you were sent to join this workspace.';
    return;
  }
  // Fragments never reach the HTTP server. Remove the key from visible browser
  // history before loading any app iframe or terminal.
  history.replaceState(null, '', location.pathname);
  try {
    const response = await fetch('/join', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({key})});
    if (!response.ok) throw Error('This sharing link is invalid or has been replaced.');
    location.replace('/');
  } catch(error) {
    document.querySelector('h1').textContent = 'Could not open workspace';
    document.querySelector('#message').textContent = error.message;
  }
})();
