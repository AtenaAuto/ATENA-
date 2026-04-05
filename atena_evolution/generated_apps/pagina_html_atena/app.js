const helloBtn = document.getElementById("helloBtn");
const output = document.getElementById("output");

helloBtn?.addEventListener("click", () => {
  if (!output) return;
  output.textContent = "🚀 Projeto pagina_html_atena (Landing Page) pronto para evoluir!";
});
