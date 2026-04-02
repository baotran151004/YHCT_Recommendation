import main

print("Loading data...")
main.load_data()

symptom = "nóng lạnh, đau đầu, buồn nôn, khô môi, ho có đờm xanh"
input_symptoms = [s.strip().lower() for s in symptom.split(",") if s.strip()]

results = []
for formula in main.knowledge_base:
    score = 0
    matched = []
    
    # Text already expanded with synonyms in load_data
    search_indications = formula.get("search_indications", "")
    search_manifestations = formula.get("search_manifestations", "")
    
    for isym in input_symptoms:
        # We also expand the input symptom to get all related terms just in case
        isym_synonyms = [isym]
        for base, aliases in main.SYMPTOM_EXPANSIONS.items():
            if isym == base or isym in aliases:
                isym_synonyms.append(base)
                isym_synonyms.extend(aliases)
                
        # Remove duplicates
        isym_synonyms = list(set(isym_synonyms))
        
        sim_ind = 1.0 if any(syn in search_indications for syn in isym_synonyms) else 0.0
        sim_man = 1.0 if any(syn in search_manifestations for syn in isym_synonyms) else 0.0
        
        if sim_ind > 0:
            score += 5
            matched.append(isym)
        elif sim_man > 0:
            score += 1
            matched.append(isym)
            
    if score > 0:
        results.append((formula["name"], score, matched))

results.sort(key=lambda x: x[1], reverse=True)
for r in results[:5]:
    print("-----")
    print("Formula:", r[0])
    print("Score:", r[1])
    print("Matched:", r[2])
