# %%

import asyncio
from nnsight import LanguageModel
from tqdm import tqdm

from sae_auto_interp.clients import get_client
from sae_auto_interp.scorers import ScorerInput, FuzzingScorer
from sae_auto_interp.utils import load_tokenized_data, execute_model
from sae_auto_interp.features import FeatureRecord
from sae_auto_interp.experiments import sample_top_and_quantiles
from sae_auto_interp.logger import logger

model = LanguageModel("openai-community/gpt2", device_map="auto", dispatch=True)
tokens = load_tokenized_data(model.tokenizer)

raw_features_path = "raw_features"
processed_features_path = "processed_features"
explanations_dir = "explanations/cot"
scorer_out_dir = "scores/cot"

def load_explanation(feature):
    explanations_path = f"{explanations_dir}/layer{feature.layer_index}_feature{feature.feature_index}.txt"

    with open(explanations_path, "r") as f:
        explanation = f.read()

    return explanation

scorer_inputs = []

for layer in range(0,12,2):
    records = FeatureRecord.from_tensor(
        tokens,
        layer,
        tokenizer=model.tokenizer,
        selected_features=list(range(50)),
        raw_dir= raw_features_path,
        processed_dir=processed_features_path,
        n_random=10,
        min_examples=200,
        max_examples=2000
    )
    
    for record in tqdm(records):

        try:
            explanation = load_explanation(record.feature)
            _, test, extra = sample_top_and_quantiles(
                record=record,
                n_train=20,
                n_test=5,
                n_quantiles=4,
                seed=22,
                n_extra=10
            )
        except Exception as e:
            logger.error(f"Failed while sampling for {record.feature}: {e}") 

        record.extra = extra

        scorer_inputs.append(
            ScorerInput(
                record=record,
                test_examples=test,
                explanation=explanation
            )
        )

client = get_client("local", "casperhansen/llama-3-70b-instruct-awq")
scorer = FuzzingScorer(client)

asyncio.run(
    execute_model(
        scorer, 
        scorer_inputs,
        output_dir=scorer_out_dir,
    )
)