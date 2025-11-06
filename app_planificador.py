import streamlit as st
import pandas as pd
import itertools
from itertools import combinations # Necesario para el modo IA
import re
# Ya no se necesita 'import random'

# --- 1. Funciones de Procesamiento de Datos (Sin cambios) ---

@st.cache_data
def load_and_preprocess_data(filepath='Horario.csv'):
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        st.error(f"Error: No se encontró el archivo {filepath}. Asegúrate de que esté en la misma carpeta.")
        return None
    except Exception as e:
        st.error(f"Error al leer el archivo {filepath}: {e}")
        return None
    df.columns = df.columns.str.strip()
    days = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado']
    required_cols = ['Semestre', 'clv_Mat', 'Materia', 'Turno', 'Grupo', 'Salón'] + days
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"Faltan las siguientes columnas en el CSV: {', '.join(missing_cols)}")
        return None
    df_tidy = df.melt(
        id_vars=['Semestre', 'clv_Mat', 'Materia', 'Turno', 'Grupo', 'Salón'],
        value_vars=days,
        var_name='Dia',
        value_name='Horario_str'
    )
    df_tidy['Horario_parsed'] = df_tidy['Horario_str'].apply(parse_time_to_minutes)
    df_tidy = df_tidy.dropna(subset=['Horario_parsed'])
    df_tidy[['Inicio_Min', 'Fin_Min']] = pd.DataFrame(
        df_tidy['Horario_parsed'].tolist(), index=df_tidy.index
    )
    df_final = df_tidy[['Semestre', 'Materia', 'Grupo', 'Turno', 'Dia', 'Inicio_Min', 'Fin_Min']].copy()
    return df_final

def parse_time_to_minutes(time_str):
    if pd.isna(time_str):
        return None
    time_str_cleaned = time_str.replace(" ", "")
    parts = re.findall(r'(\d{1,2}),(\d{2})', time_str_cleaned)
    if len(parts) == 2:
        try:
            h1, m1 = int(parts[0][0]), int(parts[0][1])
            h2, m2 = int(parts[1][0]), int(parts[1][1])
            return (h1 * 60 + m1), (h2 * 60 + m2)
        except Exception:
            return None
    return None

# --- 2. Funciones de Lógica del Planificador (Sin cambios) ---

def check_conflict(schedule):
    if not schedule:
        return False
    schedule.sort(key=lambda x: (x['Dia'], x['Inicio_Min']))
    for i in range(len(schedule) - 1):
        class1 = schedule[i]
        class2 = schedule[i+1]
        if class1['Dia'] == class2['Dia']:
            if class2['Inicio_Min'] < class1['Fin_Min']:
                return True
    return False

def calculate_gaps(schedule):
    if not schedule:
        return 0
    schedule.sort(key=lambda x: (x['Dia'], x['Inicio_Min']))
    total_gap = 0
    for i in range(len(schedule) - 1):
        class1 = schedule[i]
        class2 = schedule[i+1]
        if class1['Dia'] == class2['Dia']:
            gap = class2['Inicio_Min'] - class1['Fin_Min']
            if gap > 0:
                total_gap += gap
    return total_gap

def find_schedules(df_processed, subject_list, turno_filter):
    materias_en_csv = df_processed['Materia'].unique()
    materias_invalidas = [s for s in subject_list if s not in materias_en_csv]
    if materias_invalidas:
        return None, materias_invalidas, "INVALID_NAME"

    all_subject_groups = []
    materias_sin_grupos_en_turno = [] 
    
    for subject_name in subject_list:
        df_subject = df_processed[df_processed['Materia'] == subject_name]
        
        if turno_filter == 'Matutino (M)':
            df_subject_filtered = df_subject[df_subject['Turno'] == 'M']
        elif turno_filter == 'Tarde (T)':
            df_subject_filtered = df_subject[df_subject['Turno'] == 'T']
        else: # 'Mixto'
            df_subject_filtered = df_subject
            
        grupos_unicos = df_subject_filtered['Grupo'].unique()
        
        if len(grupos_unicos) == 0:
            materias_sin_grupos_en_turno.append(subject_name)
            continue 
        
        subject_options = []
        for grupo in grupos_unicos:
            clases_del_grupo = df_processed[
                (df_processed['Materia'] == subject_name) &
                (df_processed['Grupo'] == grupo)
            ].to_dict('records')
            
            subject_options.append({'Materia': subject_name, 'Grupo': grupo, 'Clases': clases_del_grupo})
        all_subject_groups.append(subject_options)
    
    if materias_sin_grupos_en_turno:
        return None, materias_sin_grupos_en_turno, "NO_GROUPS_IN_SHIFT"
        
    if not all_subject_groups or len(all_subject_groups) != len(subject_list):
         return [], None, None

    all_combinations = list(itertools.product(*all_subject_groups))
    
    valid_schedules = []
    for combination in all_combinations:
        full_schedule = []
        for group_info in combination:
            full_schedule.extend(group_info['Clases'])
            
        if not check_conflict(full_schedule):
            gap_score = calculate_gaps(full_schedule)
            valid_schedules.append((gap_score, combination))

    valid_schedules.sort(key=lambda x: x[0])
    return valid_schedules, None, None

# --- 3. Funciones de Visualización (Sin cambios) ---

def format_minutes_to_time(minutes):
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"

def display_schedule(schedule_tuple, index):
    gap_score, combination = schedule_tuple
    st.subheader(f"Opción {index+1} (Puntaje de horas libres: {gap_score} min)")
    summary_data = []
    full_schedule = []
    for group_info in combination:
        summary_data.append({'Materia': group_info['Materia'], 'Grupo': group_info['Grupo']})
        full_schedule.extend(group_info['Clases'])
    st.table(pd.DataFrame(summary_data))
    full_schedule.sort(key=lambda x: (['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado'].index(x['Dia']), x['Inicio_Min']))
    schedule_by_day = {day: [] for day in ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado']}
    for clase in full_schedule:
        schedule_by_day[clase['Dia']].append(clase)
    st.markdown("---")
    cols = st.columns(6)
    days_list = ['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado']
    for i, day in enumerate(days_list):
        with cols[i]:
            st.markdown(f"**{day}**")
            if not schedule_by_day[day]:
                st.caption("Libre")
            else:
                for clase in schedule_by_day[day]:
                    start = format_minutes_to_time(clase['Inicio_Min'])
                    end = format_minutes_to_time(clase['Fin_Min'])
                    st.write(f"{start} - {end}")
                    st.caption(f"{clase['Materia']}")
    st.markdown("---")

# --- 4. Nueva Función Ayudante de IA (Sin cambios) ---

def get_available_optatives(df, turno):
    """Filtra las optativas (Sem 0) por turno y cuenta sus grupos."""
    df_sem_0 = df[df['Semestre'] == 0].copy()
    
    if turno == 'Matutino (M)':
        df_filtered = df_sem_0[df_sem_0['Turno'] == 'M']
    elif turno == 'Tarde (T)':
        df_filtered = df_sem_0[df_sem_0['Turno'] == 'T']
    else: # 'Mixto'
        df_filtered = df_sem_0
        
    flexibility = df_filtered.groupby('Materia')['Grupo'].nunique().sort_values(ascending=False)
    
    return flexibility # Devuelve una Serie de Pandas (Materia -> Nro. de Grupos)


# --- 5. Ejecución Principal de la App (MODIFICADA) ---

TOP_N_FLEXIBLES = 8

def run_app():
    st.set_page_config(layout="wide")
    st.title("Planificador de Horarios 🧠")
    
    df_processed = load_and_preprocess_data('Horario.csv')
    
    if df_processed is not None:
        
        st.info("Selecciona el turno y luego elige tus materias por semestre (máx. 7 total).")
        
        selected_turno = st.radio(
            "Elige el turno:",
            ('Mixto', 'Matutino (M)', 'Tarde (T)'),
            horizontal=True
        )
        
        # --- Lógica de selección de materias ---
        mandatory_subjects = []
        manual_optativas = []
        
        optativa_config = {
            "mode": "Manual", # Manual o Inteligente
            "count": 1
        }

        semestres_disponibles = sorted(df_processed['Semestre'].unique())
        
        for sem in semestres_disponibles:
            
            # --- Lógica para Optativas (Semestre 0) ---
            if sem == 0:
                with st.expander("Optativas (Semestre 0)"):
                    # Elige el modo
                    optativa_config["mode"] = st.selectbox(
                        "Modo de selección de optativas:",
                        ("Manual", "Inteligente (Mejor Ajuste) 🧠") # <-- Opción "Aleatorio" eliminada
                    )

                    if optativa_config["mode"] == "Manual":
                        # Modo Manual: Muestra el multiselector
                        flex_data = get_available_optatives(df_processed, selected_turno)
                        if flex_data.empty:
                            st.caption(f"No hay optativas para el turno '{selected_turno}'.")
                        else:
                            # Preparamos la lista de opciones SIN el conteo de grupos
                            options_manual = list(flex_data.index) # <-- Cambio aquí
                            
                            manual_optativas = st.multiselect(
                                label="Selecciona tus optativas manualmente:",
                                options=options_manual, # <-- Se usa la lista limpia
                                key="sem_0_manual"
                            )
                            # No se necesita extraer, los nombres ya están limpios

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
                        selected = st.multiselect(
                            label=f"Materias de {label}",
                            options=subjects_in_sem,
                            key=f"sem_{sem}"
                        )
                        mandatory_subjects.extend(selected)
        
        # --- Lógica de preparación ANTES del botón ---
        
        final_subject_list = list(mandatory_subjects)
        error_msg = None
        num_to_select = optativa_config["count"]
        optativas_flex_data = get_available_optatives(df_processed, selected_turno)

        if optativa_config["mode"] == "Manual":
            final_subject_list.extend(manual_optativas)
        
        # El elif de "Aleatorio" se eliminó
        
        # --- Contador Total ---
        total_count_base = len(mandatory_subjects)
        if optativa_config["mode"] == "Manual":
            total_count = len(final_subject_list)
        else: # Solo queda "Inteligente"
            total_count = total_count_base + optativa_config["count"]
            
        st.subheader(f"Total de materias seleccionadas: {total_count} / 7")
        if total_count > 7:
            error_msg = f"¡Límite excedido! Has seleccionado {total_count} materias. El máximo es 7."
        
        if error_msg:
            st.error(error_msg)

        # --- Lógica del Botón ---
        if st.button("Encontrar mejor horario"):
            if total_count == 0:
                st.warning("Por favor, selecciona al menos una materia.")
            elif error_msg:
                 st.error(f"No se puede buscar. Corrige el error: {error_msg}")
            
            # --- MODO MANUAL ---
            elif optativa_config["mode"] == "Manual":
                with st.spinner(f"Buscando horarios en turno '{selected_turno}'..."):
                    schedules, error_list, error_type = find_schedules(
                        df_processed, 
                        final_subject_list,
                        selected_turno
                    )
                
                if error_type == "INVALID_NAME":
                    st.error(f"Error: Las siguientes materias no se encontraron: {', '.join(error_list)}")
                elif error_type == "NO_GROUPS_IN_SHIFT":
                    st.error(f"Error: Estas materias no tienen grupos en el turno '{selected_turno}': {', '.join(error_list)}")
                elif not schedules:
                    st.warning(f"No se encontró ningún horario compatible (sin conflictos) con las materias y el turno seleccionados.")
                else:
                    st.success(f"¡Se encontraron {len(schedules)} horarios compatibles!")
                    st.markdown(f"Mostrando los 3 mejores (con menos horas libres):")
                    for i, schedule_tuple in enumerate(schedules[:3]):
                        display_schedule(schedule_tuple, i)
            
            # --- MODO INTELIGENTE (Lógica de IA) ---
            elif optativa_config["mode"] == "Inteligente (Mejor Ajuste) 🧠":
                
                top_flexible_optatives = list(optativas_flex_data.head(TOP_N_FLEXIBLES).index)
                
                if len(top_flexible_optatives) < num_to_select:
                    st.error(f"Error: Pediste {num_to_select} optativas, pero solo hay {len(top_flexible_optatives)} disponibles en total en el turno '{selected_turno}' para analizar.")
                else:
                    optativa_combinations = list(combinations(top_flexible_optatives, num_to_select))
                    st.info(f"Modo IA: Analizando {len(optativa_combinations)} combinaciones de las {len(top_flexible_optatives)} optativas más flexibles...")
                    
                    best_overall_schedule = None
                    best_overall_score = float('inf')
                    progress_bar = st.progress(0)
                    
                    for i, opt_combo in enumerate(optativa_combinations):
                        current_subject_list = mandatory_subjects + list(opt_combo)
                        schedules, _, _ = find_schedules(df_processed, current_subject_list, selected_turno)
                        
                        if schedules:
                            best_schedule_for_this_combo = schedules[0]
                            score = best_schedule_for_this_combo[0]
                            
                            if score < best_overall_score:
                                best_overall_score = score
                                best_overall_schedule = best_schedule_for_this_combo
                        
                        progress_bar.progress((i + 1) / len(optativa_combinations))
                    
                    progress_bar.empty()
                    
                    if best_overall_schedule:
                        st.success("¡La IA encontró el horario óptimo! 🤖✨")
                        display_schedule(best_overall_schedule, 0)
                    else:
                        st.warning("La IA no pudo encontrar ningún horario compatible con las materias obligatorias y las optativas más flexibles.")

if __name__ == "__main__":
    run_app()
