document.addEventListener('DOMContentLoaded', function () {
    const archivoSubir = document.getElementById('subirArchivo');
    const botonAnalizar = document.getElementById('botonAnalizar');
    const nombresArchivosSeleccionadosDiv = document.getElementById('nombresArchivosSeleccionados');
    const cantidadArchivosDiv = document.getElementById('cantidadArchivos');
    const resultadosAnalisisSection = document.getElementById('resultados-analisis');
    const tablaResultadosContainer = document.getElementById('tabla-resultados-container');
    const descargarCsvButton = document.getElementById('descargar-csv');
    const columnFilterControls = document.getElementById('column-filter-controls');
    const imagePlaceholder = document.querySelector('.image-placeholder');

    archivoSubir.addEventListener('change', function () {
        nombresArchivosSeleccionadosDiv.innerHTML = '';
        const archivos = this.files;
        cantidadArchivosDiv.textContent = archivos.length;

        if (archivos.length > 51) {
            alert('Has seleccionado más de 51 archivos. Por favor, selecciona un máximo de 51.');
            archivoSubir.value = '';
            cantidadArchivosDiv.textContent = 0;
            return;
        }

        if (archivos.length > 0) {
            const listaNombres = document.createElement('ul');
            for (let i = 0; i < archivos.length; i++) {
                const nombreArchivo = archivos[i].name;
                const listItem = document.createElement('li');
                listItem.textContent = nombreArchivo;
                listaNombres.appendChild(listItem);
            }
            nombresArchivosSeleccionadosDiv.appendChild(listaNombres);
        }
    });

    botonAnalizar.addEventListener('click', function () {
        const archivos = archivoSubir.files;
        if (archivos.length > 0 && archivos.length <= 51) {
            // Aquí iría la lógica para enviar los archivos al backend para el análisis.
            // Por ejemplo, usando la función fetch:
            const formData = new FormData();
            for (let i = 0; i < archivos.length; i++) {
                formData.append('pdf', archivos[i]);
            }

            fetch('/analyze', { // Reemplaza '/api/analizar' con la URL de tu backend
                enctype: "multipart/form-data",
                method: 'POST',
                body: formData
            })
                .then(response => {
                    return response.json()
                })
                .then(resultados => {
                    console.log({ resultados })
                    mostrarResultados(resultados); // Procesar y mostrar los resultados del backend
                    imagePlaceholder.style.display = 'none';
                })
                .catch(error => {
                    console.error('Error al enviar los archivos al backend:', { error });
                    alert('Ocurrió un error al iniciar el análisis.');
                });

            resultadosAnalisisSection.style.display = 'block';
            descargarCsvButton.style.display = 'block';

        } else if (archivos.length > 51) {
            alert('Por favor, selecciona un máximo de 51 archivos para analizar.');
        } else {
            alert('Por favor, selecciona al menos un archivo para analizar.');
        }
    });

    function mostrarResultados(resultados) {
        tablaResultadosContainer.innerHTML = '';
        columnFilterControls.innerHTML = '';

        if (resultados && resultados.length > 0) {
            const tabla = document.createElement('table');
            const thead = document.createElement('thead');
            const tbody = document.createElement('tbody');
            const encabezados = Object.keys(resultados[0]);
            console.log({ encabezados })
            const encabezadoFila = document.createElement('tr');
            encabezados.forEach(encabezado => {
                const th = document.createElement('th');
                th.textContent = encabezado;
                th.setAttribute('data-columna', encabezado.replace(/ /g, ''));
                encabezadoFila.appendChild(th);

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.id = `filtro-${encabezado.replace(/ /g, '')}`;
                checkbox.value = encabezado.replace(/ /g, '');
                checkbox.checked = true;

                const label = document.createElement('label');
                label.htmlFor = `filtro-${encabezado.replace(/ /g, '')}`;
                label.textContent = encabezado;

                const filtroControl = document.createElement('div');
                filtroControl.appendChild(checkbox);
                filtroControl.appendChild(label);
                columnFilterControls.appendChild(filtroControl);

                checkbox.addEventListener('change', function () {
                    const columna = this.value;
                    const visible = this.checked;
                    const columnasTabla = tabla.querySelectorAll(`th[data-columna="${columna}"], td[data-columna="${columna}"]`);
                    columnasTabla.forEach(columnaElement => {
                        columnaElement.style.display = visible ? '' : 'none';
                    });
                });
            });
            thead.appendChild(encabezadoFila);
            tabla.appendChild(thead);

            resultados.forEach(resultado => {
                const fila = document.createElement('tr');
                encabezados.forEach(encabezado => {
                    const td = document.createElement('td');
                    td.textContent = resultado[encabezado];
                    td.setAttribute('data-columna', encabezado.replace(/ /g, ''));
                    fila.appendChild(td);
                });
                tbody.appendChild(fila);
            });
            tabla.appendChild(tbody);
            tablaResultadosContainer.appendChild(tabla);
        } else {
            tablaResultadosContainer.innerHTML = '<p>No se recibieron resultados del análisis.</p>';
        }
    }

    descargarCsvButton.addEventListener('click', function () {
        const tabla = tablaResultadosContainer.querySelector('table');
        if (tabla && tabla.querySelector('tbody tr')) {
            generarYDescargarCSV(tabla);
        } else {
            alert('No hay resultados para descargar.');
        }
    });

    function generarYDescargarCSV(tabla) {
        let csv = [];
        const filas = tabla.querySelectorAll('tr');
        const encabezados = [];
        const thElements = tabla.querySelectorAll('thead th');
        thElements.forEach(th => {
            encabezados.push(th.textContent.replace(/,/g, ''));
        });
        csv.push(encabezados.join(','));

        for (let i = 1; i < filas.length; i++) {
            const celdas = filas[i].querySelectorAll('td');
            let filaCsv = [];
            for (let j = 0; j < celdas.length; j++) {
                filaCsv.push(celdas[j].textContent.replace(/,/g, ''));
            }
            csv.push(filaCsv.join(','));
        }
        descargarArchivoCSV(csv.join('\n'), 'resultados_analisis.csv');
    }

    function descargarArchivoCSV(csv, nombreArchivo) {
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = nombreArchivo;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }
});