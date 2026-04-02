import main

print("Loading data...")
main.load_data()

symptom = "nóng lạnh, đau đầu, buồn nôn, khô môi, ho có đờm xanh"
print("Input:", symptom)

input_symptoms = [s.strip().lower() for s in symptom.split(",") if s.strip()]
input_embeddings = main.model.encode(input_symptoms, convert_to_tensor=True)

THRESHOLD = 0.50

results = []
for formula in main.knowledge_base:
    f_cat = formula.get("category", "").lower()
    score = 0
    matched = []
    
    search_indications = formula.get("search_indications", "")
    search_manifestations = formula.get("search_manifestations", "")
    ind_emb = formula.get("indications_emb")
    man_emb = formula.get("manifestations_emb")
    
    for i, isym in enumerate(input_symptoms):
        isym_emb = input_embeddings[i]
        sym_score = 0
        
        sim_ind = 0.0
        if isym in search_indications:
            sim_ind = 1.0
        elif ind_emb is not None:
            sim_ind = main.util.cos_sim(isym_emb, ind_emb).item()
            
        sim_man = 0.0
        if isym in search_manifestations:
            sim_man = 1.0
        elif man_emb is not None:
            sim_man = main.util.cos_sim(isym_emb, man_emb).item()
            
        if sim_ind >= THRESHOLD:
            sym_score += 5 * sim_ind
        elif sim_man >= THRESHOLD:
            sym_score += 1 * sim_man
            
        if sym_score > 0:
            score += sym_score
            matched.append((isym, sim_ind, sim_man))

    results.append((formula["name"], score, matched, search_indications, search_manifestations))

results.sort(key=lambda x: x[1], reverse=True)
for r in results[:5]:
    print("-----")
    print("Formula:", r[0])
    print("Score:", r[1])
    print("Matched:", r[2])
    # print("Ind:", r[3])
    # print("Man:", r[4])
