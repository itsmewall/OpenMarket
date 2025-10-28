(function(){
  // Atalhos: F2 abre venda, F8 pagar, F9 cancelar, Enter adiciona
  document.addEventListener('keydown', function(e){
    const saleId = new URLSearchParams(location.search).get('sale_id');
    if (e.code === 'F2' && document.getElementById('btnOpen')) {
      e.preventDefault();
      document.getElementById('btnOpen').click();
    }
    if (!saleId) return;
    if (e.code === 'Enter' && document.getElementById('formAdd')) {
      const active = document.activeElement;
      if (active && (active.tagName === 'INPUT' || active.tagName === 'SELECT')) return;
      e.preventDefault();
      document.getElementById('formAdd').submit();
    }
    if (e.code === 'F8' && document.getElementById('btnPay')) {
      e.preventDefault();
      document.getElementById('btnPay').click();
    }
    if (e.code === 'F9' && document.getElementById('btnCancel')) {
      e.preventDefault();
      document.getElementById('btnCancel').click();
    }
  });
})();
