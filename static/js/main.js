document.getElementById("btnBuscar").addEventListener("click", () => {
  const nombre = document.getElementById("inputNombre").value.trim();
  if (!nombre) return;

  fetch(`/customer?name=${nombre}`)
    .then((res) => res.json())
    .then((cliente) => {
      if (cliente.error) return alert(cliente.error);
      document.getElementById("clienteNombre").textContent = cliente.name;
      document.getElementById("clienteEdad").textContent = cliente.age;
      document.querySelector("[name='types']").value = cliente.preferences.types.join(", ");
      document.querySelector("[name='flavor_profiles']").value = cliente.preferences.flavor_profiles.join(", ");
      document.querySelector("[name='origins']").value = cliente.preferences.origins.join(", ");
      document.getElementById("btnRecomendar").dataset.nombre = cliente.name;
      document.getElementById("seccionCliente").classList.remove("d-none");

      cargarHistorial(cliente.name);
    });
});

document.getElementById("formPreferencias").addEventListener("submit", (e) => {
  e.preventDefault();
  const nombre = document.getElementById("clienteNombre").textContent;
  const prefs = {
    types: document.querySelector("[name='types']").value.split(",").map((x) => x.trim()),
    flavor_profiles: document.querySelector("[name='flavor_profiles']").value.split(",").map((x) => x.trim()),
    origins: document.querySelector("[name='origins']").value.split(",").map((x) => x.trim()),
  };

  fetch("/customer/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: nombre, preferences: prefs }),
  })
    .then((res) => res.json())
    .then((data) => {
      alert(data.success ? "Preferencias actualizadas" : "Error al guardar");
    });
});

document.getElementById("btnRecomendar").addEventListener("click", () => {
  const nombre = document.getElementById("btnRecomendar").dataset.nombre;
  fetch(`/recommendations?name=${nombre}`)
    .then((res) => res.json())
    .then((recs) => {
      const ul = document.getElementById("listaRecomendaciones");
      ul.innerHTML = "";
      recs.forEach((r) => {
        const li = document.createElement("li");
        li.className = "list-group-item";
        li.textContent = `${r.name} (${r.type}, ${r.origin}) - match ${(r.similarity * 100).toFixed(1)}%`;
        ul.appendChild(li);
      });
      cargarHistorial(nombre);
    });
});

function cargarHistorial(nombre) {
  fetch(`/history?name=${nombre}`)
    .then((res) => res.json())
    .then((data) => {
      const ul = document.getElementById("listaHistorial");
      ul.innerHTML = "";
      data.forEach((item) => {
        const li = document.createElement("li");
        li.className = "list-group-item";
        li.textContent = `${new Date(item.date).toLocaleString()} - ${item.recommendations.length} recomendaciones`;
        ul.appendChild(li);
      });
    });
}

document.getElementById("btnRecomendarTodos").addEventListener("click", () => {
  fetch("/recommend_all", {
    method: "POST"
  })
  .then(res => res.json())
  .then(data => {
    const ul = document.getElementById("resultadosMasivos");
    ul.innerHTML = "";
    if (data.detalle) {
      data.detalle.forEach(item => {
        const li = document.createElement("li");
        li.className = "list-group-item";
        li.textContent = `✔ ${item.cliente}: ${item.total} recomendación(es)`;
        ul.appendChild(li);
      });
    } else {
      ul.innerHTML = "<li class='list-group-item text-danger'>Error al procesar recomendaciones.</li>";
    }
  });
});
