function abrirModal(id) {
  document.getElementById(id).classList.remove('hidden');
  document.getElementById(id).classList.add('flex');
}
function fecharModal(id) {
  document.getElementById(id).classList.remove('flex');
  document.getElementById(id).classList.add('hidden');
}

document.getElementById('btnAddPacientes')?.addEventListener('click', () => abrirModal('modalAddPacientes'));

document.getElementById('closeAddPacientes')?.addEventListener('click', () => fecharModal('modalAddPacientes'));
document.getElementById('closeUpdatePacientes')?.addEventListener('click', () => fecharModal('modalUpdatePacientes'));
document.getElementById('closeModalReceita')?.addEventListener('click', () => fecharModal('modalReceita'));

function abrirModalUpdate(id) {
  const modal = document.getElementById('modalUpdatePacientes');
  modal.querySelector('form').action = `/atualizar_paciente/${id}/`;
  abrirModal('modalUpdatePacientes');
}
