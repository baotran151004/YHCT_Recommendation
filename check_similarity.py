from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

queries = ["nóng lạnh", "đau đầu", "buồn nôn", "khô môi", "ho có đờm xanh"]
texts = ["trị nấc cụt tỳ vị hư hàn bụng lạnh", "bổ âm, chữa nóng trong xương", "viêm màng phổi, ho gà"]

emb_queries = model.encode(queries, convert_to_tensor=True)
emb_texts = model.encode(texts, convert_to_tensor=True)

print("Similarity Matrix:")
for i, q in enumerate(queries):
    for j, t in enumerate(texts):
        sim = util.cos_sim(emb_queries[i], emb_texts[j]).item()
        print(f"'{q}' vs '{t}' => {sim:.3f}")
