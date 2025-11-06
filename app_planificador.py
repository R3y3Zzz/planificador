import streamlit as st
import pandas as pd
import itertools
from itertools import combinations # Necesario para el modo IA
import re
# Ya no se necesita 'import random'

# --- 1. Funciones de Procesamiento de Datos ---

@st.cache_data
def load_and_preprocess_data(filepath='Horario.csv'):
    """
    Carga el archivo CSV, lo procesa y lo transforma en un formato "tidy" (ordenado).

    Utiliza st.cache_data para evitar recargar y procesar el archivo cada vez
    que el usuario interactúa con la UI.

    Args:
        filepath (str): La ruta al archivo CSV (por defecto 'Horario.csv').

    Returns:
        pd.DataFrame | None: Un DataFrame procesado y listo para el análisis,
        o None si ocurre un error (archivo no encontrado, columnas faltantes, etc.).
    """
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        st.error(f"Error: No se encontró el archivo {filepath}. Asegúrate de que esté en la misma carpeta.")
        return None
    except Exception as e:
        st.error(f"Error al leer el archivo {filepath}: {e}")
        return None

    # --- Limpieza y Validación ---
    df.columns = df.columns.str.strip()
    days = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado']
    required_cols = ['Semestre', 'clv_Mat', 'Materia', 'Turno', 'Grupo', 'Salón'] + days
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        st.error(f"Faltan las siguientes columnas en el CSV: {', '.join(missing_cols)}")
        return None

    # --- Transformación (Melt) ---
    # Convierte el formato "ancho" (columnas de días) a "largo" (una columna 'Dia' y 'Horario_str')
    df_tidy = df.melt(
        id_vars=['Semestre', 'clv_Mat', 'Materia', 'Turno', 'Grupo', 'Salón'],
        value_vars=days,
        var_name='Dia',
        value_name='Horario_str'
    )

    # --- Parseo de Horas ---
    df_tidy['Horario_parsed'] = df_tidy['Horario_str'].apply(parse_time_to_minutes)
    df_tidy = df_tidy.dropna(subset=['Horario_parsed']) # Elimina filas donde el horario era NaN o inválido

    # Convierte la columna de tuplas '(inicio, fin)' en dos columnas separadas
    df_tidy[['Inicio_Min', 'Fin_Min']] = pd.DataFrame(
        df_tidy['Horario_parsed'].tolist(), index=df_tidy.index
    )

    # --- Selección Final ---
    # Selecciona solo las columnas necesarias para la lógica del planificador
    df_final = df_tidy[['Semestre', 'Materia', 'Grupo', 'Turno', 'Dia', 'Inicio_Min', 'Fin_Min']].copy()
    return df_final

def parse_time_to_minutes(time_str):
    """
    Convierte una cadena de texto de horario (ej: "11,30 - 13,00") en minutos.

    Args:
        time_str (str): La cadena de texto del horario.

    Returns:
        tuple(int, int) | None: Una tupla (minutos_inicio, minutos_fin) o None si
        la cadena es nula o no tiene el formato esperado.
    """
    if pd.isna(time_str):
        return None
    
    # Limpia la cadena (elimina espacios)
    time_str_cleaned = time_str.replace(" ", "")
    
    # Busca patrones como 'HH,MM' usando expresiones regulares
    parts = re.findall(r'(\d{1,2}),(\d{2})', time_str_cleaned)
    
    if len(parts) == 2: # Debe encontrar exactamente dos pares (inicio y fin)
        try:
            h1, m1 = int(parts[0][0]), int(parts[0][1])
            h2, m2 = int(parts[1][0]), int(parts[1][1])
            # Convierte horas y minutos a minutos totales
            return (h1 * 60 + m1), (h2 * 60 + m2)
        except Exception:
            return None # Error en la conversión a entero
    return None

# --- 2. Funciones de Lógica del Planificador ---

def check_conflict(schedule):
    """
    Verifica si existe algún conflicto de horario (clases traslapadas) en una
    lista de clases.

    Args:
        schedule (list[dict]): Una lista de diccionarios, donde cada dict
                               representa una clase y tiene 'Dia', 'Inicio_Min' y 'Fin_Min'.

    Returns:
        bool: True si hay un conflicto, False si no hay conflictos.
    """
    if not schedule:
        return False
    
    # Ordena las clases por día y luego por hora de inicio
    schedule.sort(key=lambda x: (x['Dia'], x['Inicio_Min']))
    
    for i in range(len(schedule) - 1):
        class1 = schedule[i]
        class2 = schedule[i+1]
        
        # Solo compara clases del mismo día
        if class1['Dia'] == class2['Dia']:
            # Conflicto: Si la clase 2 empieza ANTES de que termine la clase 1
            if class2['Inicio_Min'] < class1['Fin_Min']:
                return True
    return False

def calculate_gaps(schedule):
    """
    Calcula el "puntaje de horas libres" (tiempo muerto) total en un horario.
    Este puntaje es la suma de todos los minutos entre clases en un mismo día.
    Un puntaje más bajo significa un horario más compacto.

    Args:
        schedule (list[dict]): Una lista de clases (diccionarios).

    Returns:
        int: El total de minutos libres (gap) en el horario.
    """
    if not schedule:
        return 0
        
    # Ordena para asegurar que las comparaciones sean correctas
    schedule.sort(key=lambda x: (x['Dia'], x['Inicio_Min']))
    
    total_gap = 0
    for i in range(len(schedule) - 1):
        class1 = schedule[i]
        class2 = schedule[i+1]
        
        # Solo calcula gaps en el mismo día
        if class1['Dia'] == class2['Dia']:
            gap = class2['Inicio_Min'] - class1['Fin_Min']
            if gap > 0: # Solo suma si es un gap positivo
                total_gap += gap
    return total_gap

def find_schedules(df_processed, subject_list, turno_filter):
    """
    El motor principal. Encuentra todas las combinaciones de horarios posibles
    para una lista de materias y un filtro de turno, eliminando las que
    tienen conflictos.

    Args:
        df_processed (pd.DataFrame): El DataFrame limpio de load_and_preprocess_data.
        subject_list (list[str]): La lista de nombres de materias seleccionadas.
        turno_filter (str): 'Mixto', 'Matutino (M)' o 'Tarde (T)'.

    Returns:
        tuple: (valid_schedules, error_list, error_type)
            - valid_schedules (list): Lista de tuplas (gap_score, combination) ordenadas
                                      de mejor a peor (puntaje más bajo primero).
            - error_list (list | None): Lista de materias que causaron el error.
            - error_type (str | None): 'INVALID_NAME' o 'NO_GROUPS_IN_SHIFT'.
    """
    # 1. Validación de Nombres de Materias
    materias_en_csv = df_processed['Materia'].unique()
    materias_invalidas = [s for s in subject_list if s not in materias_en_csv]
    if materias_invalidas:
        return None, materias_invalidas, "INVALID_NAME"

    all_subject_groups = [] # Lista de listas (una por materia)
    materias_sin_grupos_en_turno = [] 
    
    # 2. Filtrado por Materia y Turno
    for subject_name in subject_list:
        df_subject = df_processed[df_processed['Materia'] == subject_name]
        
        # Aplicar filtro de turno
        if turno_filter == 'Matutino (M)':
            df_subject_filtered = df_subject[df_subject['Turno'] == 'M']
        elif turno_filter == 'Tarde (T)':
            df_subject_filtered = df_subject[df_subject['Turno'] == 'T']
        else: # 'Mixto'
            df_subject_filtered = df_subject
            
        grupos_unicos = df_subject_filtered['Grupo'].unique()
        
        if len(grupos_unicos) == 0:
            # Error: La materia existe, pero no en el turno seleccionado
            materias_sin_grupos_en_turno.append(subject_name)
            continue 
        
        # 3. Agrupar clases por grupo
        subject_options = []
        for grupo in grupos_unicos:
            clases_del_grupo = df_processed[
                (df_processed['Materia'] == subject_name) &
                (df_processed['Grupo'] == grupo)
            ].to_dict('records')
            
            # Cada 'opción' es un grupo con todas sus clases asociadas
            subject_options.append({'Materia': subject_name, 'Grupo': grupo, 'Clases': clases_del_grupo})
        
        all_subject_groups.append(subject_options) # Añade la lista de grupos para esta materia
    
    if materias_sin_grupos_en_turno:
        return None, materias_sin_grupos_en_turno, "NO_GROUPS_IN_SHIFT"
        
    if not all_subject_groups or len(all_subject_groups) != len(subject_list):
         # Si la lista está vacía o no coincide (lo cual no debería pasar si las validaciones previas funcionan)
       return [], None, None

    # 4. Generar Combinaciones (Producto Cartesiano)
    # Si tenemos 3 materias, con 2, 3 y 2 grupos respectivamente,
    # esto crea 2 * 3 * 2 = 12 combinaciones totales.
    all_combinations = list(itertools.product(*all_subject_groups))
    
    valid_schedules = []
    
    # 5. Validar Combinaciones
    for combination in all_combinations:
        full_schedule = [] # El horario completo para esta combinación
        
        # 'combination' es una tupla de dicts, ej: ({MateriaA, Gpo1, Clases}, {MateriaB, Gpo3, Clases})
        for group_info in combination:
            full_schedule.extend(group_info['Clases'])
            
        # 6. Revisar Conflictos y Calcular Puntaje
        if not check_conflict(full_schedule):
            gap_score = calculate_gaps(full_schedule)
            valid_schedules.append((gap_score, combination))

    # 7. Ordenar por mejor puntaje (más bajo)
    valid_schedules.sort(key=lambda x: x[0])
    return valid_schedules, None, None

# --- 3. Funciones de Visualización ---

def format_minutes_to_time(minutes):
    """
    Función ayudante para convertir minutos a formato HH:MM.

    Args:
        minutes (int): Total de minutos desde la medianoche (ej: 570).

    Returns:
        str: El tiempo formateado (ej: "09:30").
    """
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"

def display_schedule(schedule_tuple, index):
    """
    Renderiza un horario completo en la interfaz de Streamlit,
    mostrando el puntaje, la tabla de grupos y el horario por día.

    Args:
        schedule_tuple (tuple): La tupla (gap_score, combination) devuelta por find_schedules.
        index (int): El número de opción a mostrar (ej: 0 para "Opción 1").
    """
    gap_score, combination = schedule_tuple
    st.subheader(f"Opción {index+1} (Puntaje de horas libres: {gap_score} min)")
    
    # 1. Tabla Resumen (Materia y Grupo)
    summary_data = []
    full_schedule = []
    for group_info in combination:
        summary_data.append({'Materia': group_info['Materia'], 'Grupo': group_info['Grupo']})
        full_schedule.extend(group_info['Clases'])
    st.table(pd.DataFrame(summary_data))
    
    # 2. Ordenar el horario completo por día y hora
    days_order = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado']
    full_schedule.sort(key=lambda x: (days_order.index(x['Dia']), x['Inicio_Min']))
    
    # 3. Organizar clases por día
    schedule_by_day = {day: [] for day in days_order}
    for clase in full_schedule:
        schedule_by_day[clase['Dia']].append(clase)
        
    st.markdown("---")
    
    # 4. Mostrar en 6 columnas
    cols = st.columns(6)
    for i, day in enumerate(days_order):
        with cols[i]:
            st.markdown(f"**{day}**")
            if not schedule_by_day[day]:
                st.caption("Libre")
            else:
                for clase in schedule_by_day[day]:
                    start = format_minutes_to_time(clase['Inicio_Min'])
                    end = format_minutes_to_time(clase['Fin_Min'])
                    st.write(f"{start} - {end}")
                    st.caption(f"{clase['Materia']}") # Muestra el nombre de la materia debajo
    st.markdown("---")

# --- 4. Nueva Función Ayudante de IA ---

def get_available_optatives(df, turno):
    """
    Filtra las materias optativas (Semestre 0) según el turno seleccionado
    y cuenta cuántos grupos únicos tiene cada una.

    Args:
        df (pd.DataFrame): El DataFrame procesado.
        turno (str): 'Mixto', 'Matutino (M)' o 'Tarde (T)'.

    Returns:
        pd.Series: Una Serie de Pandas con 'Materia' como índice y el conteo
                   de 'Grupo' como valor, ordenada descendentemente.
                   (Las materias con más grupos aparecen primero).
    """
    df_sem_0 = df[df['Semestre'] == 0].copy()
    
    if turno == 'Matutino (M)':
        df_filtered = df_sem_0[df_sem_0['Turno'] == 'M']
    elif turno == 'Tarde (T)':
        df_filtered = df_sem_0[df_sem_0['Turno'] == 'T']
    else: # 'Mixto'
        df_filtered = df_sem_0
        
    # Agrupa por materia, cuenta grupos únicos y ordena
    flexibility = df_filtered.groupby('Materia')['Grupo'].nunique().sort_values(ascending=False)
    
    return flexibility

# --- 5. Ejecución Principal de la App ---

# Constante: Limita el análisis de la IA a las N optativas más flexibles
# (con más grupos) para evitar una explosión combinatoria.
TOP_N_FLEXIBLES = 8

def run_app():
    """
    Función principal que ejecuta la aplicación Streamlit.
    Define la interfaz de usuario y maneja la lógica de los botones.
    """
    st.set_page_config(layout="wide")
    st.title("Planificador de Horarios 🧠")
    
    # Carga y procesa los datos una sola vez
    df_processed = load_and_preprocess_data('Horario.csv')
    
    if df_processed is not None:
        
        st.info("Selecciona el turno y luego elige tus materias por semestre (máx. 7 total).")
        
        # --- Configuración del Turno ---
        selected_turno = st.radio(
            "Elige el turno:",
            ('Mixto', 'Matutino (M)', 'Tarde (T)'),
            horizontal=True
        )
        
        # --- Lógica de selección de materias ---
        mandatory_subjects = [] # Materias obligatorias (Sem 1-9)
        manual_optativas = []   # Optativas seleccionadas en modo manual
        
        optativa_config = {
            "mode": "Manual", # Manual o Inteligente
            "count": 1        # Número de optativas en modo IA
        }

        semestres_disponibles = sorted(df_processed['Semestre'].unique())
        
        # Itera sobre cada semestre para crear la UI
        for sem in semestres_disponibles:
            
            # --- Lógica para Optativas (Semestre 0) ---
            if sem == 0:
                with st.expander("Optativas (Semestre 0)"):
                    # Elige el modo
                    optativa_config["mode"] = st.selectbox(
                        "Modo de selección de optativas:",
                        ("Manual", "Inteligente (Mejor Ajuste) 🧠")
                    )

                    if optativa_config["mode"] == "Manual":
                        # Modo Manual: Muestra el multiselector
                        flex_data = get_available_optatives(df_processed, selected_turno)
                        if flex_data.empty:
                            st.caption(f"No hay optativas para el turno '{selected_turno}'.")
                        else:
                            options_manual = list(flex_data.index) # Lista de nombres de materias
                            
                            manual_optativas = st.multiselect(
                                label="Selecciona tus optativas manualmente:",
                                options=options_manual,
                                key="sem_0_manual"
                            )

                    else: # Modo Inteligente
                        optativa_config["count"] = st.number_input(
                            f"¿Cuántas optativas en modo 'Inteligente' quieres?",
                            min_value=1, max_value=5, value=1, key="count"
                        )
            
            # --- Lógica para Semestres Obligatorios (1-9) ---
            else:
                label = f"Semestre {sem}"
                with st.expander(label):
                    df_sem = df_processed[df_processed['Semestre'] == sem]
                    
                    # Filtra materias del semestre por turno
                    if selected_turno == 'Matutino (M)':
                        df_sem_filtered = df_sem[df_sem['Turno'] == 'M']
                    elif selected_turno == 'Tarde (T)':
                        df_sem_filtered = df_sem[df_sem['Turno'] == 'T']
                    else:
                        df_sem_filtered = df_sem
                        
                    subjects_in_sem = sorted(df_sem_filtered['Materia'].unique())
                    
                    if not subjects_in_sem:
                        st.caption(f"No hay materias de este semestre para el turno '{selected_turno}'.")
                    else:
                        # Multiselector para las materias obligatorias
                        selected = st.multiselect(
                            label=f"Materias de {label}",
                            options=subjects_in_sem,
                            key=f"sem_{sem}"
                        )
                        mandatory_subjects.extend(selected)
        
        # --- Lógica de preparación ANTES del botón ---
        
        # Lista base de materias (obligatorias)
        final_subject_list = list(mandatory_subjects)
        error_msg = None
        
        # Obtiene las optativas disponibles para el turno
        optativas_flex_data = get_available_optatives(df_processed, selected_turno)

        if optativa_config["mode"] == "Manual":
            # Si es manual, simplemente añade las seleccionadas
            final_subject_list.extend(manual_optativas)
        
        # --- Contador Total ---
        total_count_base = len(mandatory_subjects)
        if optativa_config["mode"] == "Manual":
            total_count = len(final_subject_list)
        else: # "Inteligente"
            # El total es la suma de obligatorias + el NÚMERO de optativas IA
            total_count = total_count_base + optativa_config["count"]
            
        st.subheader(f"Total de materias seleccionadas: {total_count} / 7")
        if total_count > 7:
            error_msg = f"¡Límite excedido! Has seleccionado {total_count} materias. El máximo es 7."
        
        if error_msg:
            st.error(error_msg)

        # --- Lógica del Botón "Encontrar mejor horario" ---
        if st.button("Encontrar mejor horario"):
            if total_count == 0:
                st.warning("Por favor, selecciona al menos una materia.")
            elif error_msg:
                 st.error(f"No se puede buscar. Corrige el error: {error_msg}")
            
            # --- MODO MANUAL ---
            elif optativa_config["mode"] == "Manual":
                with st.spinner(f"Buscando horarios en turno '{selected_turno}'..."):
                    # Llama a la función principal UNA SOLA VEZ
                    schedules, error_list, error_type = find_schedules(
                        df_processed, 
                        final_subject_list,
                        selected_turno
                    )
                
                # Manejo de resultados y errores
                if error_type == "INVALID_NAME":
                    st.error(f"Error: Las siguientes materias no se encontraron: {', '.join(error_list)}")
                elif error_type == "NO_GROUPS_IN_SHIFT":
                    st.error(f"Error: Estas materias no tienen grupos en el turno '{selected_turno}': {', '.join(error_list)}")
                elif not schedules:
                    st.warning(f"No se encontró ningún horario compatible (sin conflictos) con las materias y el turno seleccionados.")
                else:
                    st.success(f"¡Se encontraron {len(schedules)} horarios compatibles!")
                    st.markdown(f"Mostrando los 3 mejores (con menos horas libres):")
                    # Muestra los 3 mejores
                    for i, schedule_tuple in enumerate(schedules[:3]):
                        display_schedule(schedule_tuple, i)
            
            # --- MODO INTELIGENTE (Lógica de IA) ---
            elif optativa_config["mode"] == "Inteligente (Mejor Ajuste) 🧠":
                
                num_to_select = optativa_config["count"]
                
                # 1. Obtiene las N optativas más flexibles (con más grupos)
                top_flexible_optatives = list(optativas_flex_data.head(TOP_N_FLEXIBLES).index)
                
                if len(top_flexible_optatives) < num_to_select:
                    st.error(f"Error: Pediste {num_to_select} optativas, pero solo hay {len(top_flexible_optatives)} disponibles en total en el turno '{selected_turno}' para analizar.")
                else:
                    # 2. Crea combinaciones de esas N optativas (ej: 8 C 2)
                    optativa_combinations = list(combinations(top_flexible_optatives, num_to_select))
                    st.info(f"Modo IA: Analizando {len(optativa_combinations)} combinaciones de las {len(top_flexible_optatives)} optativas más flexibles...")
                    
                    best_overall_schedule = None
                    best_overall_score = float('inf') # Inicia con un puntaje infinito
                    progress_bar = st.progress(0)
                    
                    # 3. Itera sobre cada combinación de OPTATIVAS
                    for i, opt_combo in enumerate(optativa_combinations):
                        # Lista de materias = Obligatorias + combinación actual de optativas
                        current_subject_list = mandatory_subjects + list(opt_combo)
                        
                        # 4. Llama a find_schedules para CADA combinación
                        schedules, _, _ = find_schedules(df_processed, current_subject_list, selected_turno)
                        
                        if schedules:
                            # 5. Obtiene el MEJOR horario de ESTA combinación
                            best_schedule_for_this_combo = schedules[0]
                            score = best_schedule_for_this_combo[0]
                            
                            # 6. Compara con el mejor puntaje global
                            if score < best_overall_score:
                                best_overall_score = score
                                best_overall_schedule = best_schedule_for_this_combo
                        
                        # Actualiza la barra de progreso
                        progress_bar.progress((i + 1) / len(optativa_combinations))
                    
                    progress_bar.empty()
                    
                    # 7. Muestra el mejor resultado de TODAS las combinaciones
                    if best_overall_schedule:
                        st.success("¡La IA encontró el horario óptimo! 🤖✨")
                        display_schedule(best_overall_schedule, 0)
                    else:
                        st.warning("La IA no pudo encontrar ningún horario compatible con las materias obligatorias y las optativas más flexibles.")

# Punto de entrada estándar de Python:
# Si el script se ejecuta directamente (no importado), llama a run_app()
if __name__ == "__main__":
    run_app()