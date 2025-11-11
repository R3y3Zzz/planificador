# Planificador de Horarios 

## 1. Descripción del Proyecto

Este proyecto es una aplicación web de Inteligencia Artificial diseñada para resolver el Problema de Satisfacción de Restricciones (CSP) de la creación de horarios académicos. 
La aplicación, construida en Python con Streamlit y Pandas, permite a los usuarios seleccionar un conjunto de materias deseadas y un turno, y calcula el horario óptimo minimizando 
las horas libres entre clases.

**Enlace a la aplicación en vivo:** [https://planificador-iappsaksay8kkzcz4mv7zm.streamlit.app/]

## 2. Características Principales

* **Filtro por Turno:** Permite elegir entre Matutino (M), Tarde (T) o Mixto.
* **Selección por Semestre:** Organiza las materias en secciones desplegables por semestre, incluyendo optativas (Semestre 0).
* **Modo de Selección de Optativas:**
    * **Manual:** El usuario elige sus optativas específicas.
    * **Inteligente (Mejor Ajuste):** El usuario indica *cuántas* optativas desea, y la IA analiza las combinaciones más flexibles para encontrar el horario global óptimo.

## 3. Componentes del Planificador de IA

Este sistema funciona como un planificador de dominio específico, siguiendo un modelo de IA clásico:

1.  **Base de Conocimiento:**
    * **Hechos:** El archivo `Horario.csv`, que define el universo de todas las materias, grupos, turnos y salones.
    * **Reglas:** `check_conflict()` - Un horario no es válido si dos clases se superponen en el mismo día y hora.
    * **Heurísticas:** `calculate_gaps()` - Una función de costo que define un "mejor" horario como aquel con el mínimo de minutos libres entre clases.

2.  **Estado Inicial:**
    * La lista de materias obligatorias seleccionadas por el usuario.
    * El turno (`M`, `T`, `Mixto`).
    * El modo de optativas (`Manual` o `Inteligente`) y la cantidad deseada.

3.  **Acciones:**
    * `Asignar(Materia, Grupo)`: La acción de seleccionar un grupo específico para una materia dada.

4.  **Condiciones (Pre/Post):**
    * **Precondición:** El grupo seleccionado debe pertenecer al turno filtrado.
    * **Postcondición:** El plan final (lista de clases) debe ser válido (retornar `False` de `check_conflict()`).

5.  **Estado Final (Meta):**
    * Un conjunto de asignaciones (un horario completo) que satisface todas las restricciones (Estado Inicial + Postcondiciones)
    * Y minimiza la función de costo heurística (las horas libres).

## 4. Algoritmos Utilizados

* **Generar y Probar:** El motor principal (`itertools.product`) genera todas las combinaciones de grupos (planes) posibles.
* **Satisfacción de Restricciones (CSP):** El filtro `check_conflict` descarta los planes inválidos.
* **Búsqueda Heurística:**
    1.  **Heurística:** Se define que las optativas "más prometedoras" son las que tienen más grupos (`get_available_optatives()`).
    2.  **Poda (Pruning):** El sistema limita su búsqueda a las `TOP_N_FLEXIBLES` (8) optativas más prometedoras, en lugar de analizar todo el catálogo.
    3.  **Optimización:** El sistema itera sobre las combinaciones de estas optativas (`itertools.combinations`) y ejecuta el "Generar y Probar" en cada
    4.  una para encontrar el óptimo global.

## 5. Problemas Durante el Desarrollo

1.  **Explosión Combinatoria:** El Modo Inteligente era computacionalmente inviable si se probaban *todas* las optativas. Se resolvió aplicando la **heurística de flexibilidad**
(Poda), reduciendo el espacio de búsqueda de miles de combinaciones a un número manejable.
3.  **Parsing de Datos:** El `Horario.csv` original tenía espacios en los nombres de las columnas (`'Semestre '`) y los horarios eran texto (`"09,00 - 11,00"`).
se resolvieron con `df.columns.str.strip()` y la función `parse_time_to_minutes`.
5.  **Manejo de Errores de Usuario:** El programa fallaba si un usuario elegía "Matutino" y una materia que solo existía en la tarde.
se implementaron manejadores de errores (`NO_GROUPS_IN_SHIFT`)


## 7. Autores y Colaboradores

* **AUTORES:** []
