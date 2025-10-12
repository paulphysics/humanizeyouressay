async function payWithPayPal(amount) {
  const res = await fetch("/paypal/create", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({amount}),
  });
  const data = await res.json();
  const approvalUrl = data.links.find(link => link.rel === "approve").href;
  window.location.href = approvalUrl;
}
