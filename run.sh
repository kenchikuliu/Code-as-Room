# python /home/pjlab/SceneAgent/Code_as_3D_Room/image_prompt_gen/batch_run_pipeline.py \
#     --images-dir /home/pjlab/SceneAgent/benchmark_input/simple_5 \
#     --output-root /home/pjlab/SceneAgent/CAR3D_output \
#     --parallel 16 \
#     --label simple --model-tag gpt55 \
#     --max-concurrent 5  

# python /home/pjlab/SceneAgent/Code_as_3D_Room/image_prompt_gen/batch_run_pipeline.py \
#     --images-dir /home/pjlab/SceneAgent/benchmark_input/mid_16 \
#     --output-root /home/pjlab/SceneAgent/CAR3D_output \
#     --parallel 16 \
#     --label mid --model-tag gpt55 \
#     --max-concurrent 5  

# python /home/pjlab/SceneAgent/Code_as_3D_Room/image_prompt_gen/batch_run_pipeline.py \
#     --images-dir /home/pjlab/SceneAgent/benchmark_input/hard_11 \
#     --output-root /home/pjlab/SceneAgent/CAR3D_output \
#     --parallel 16 \
#     --label hard --model-tag gpt55 \
#     --max-concurrent 5  


python /home/pjlab/SceneAgent/Code_as_3D_Room/image_prompt_gen/batch_run_pipeline.py \
    --images-dir /home/pjlab/SceneAgent/benchmark_input/special_10 \
    --output-root /home/pjlab/SceneAgent/CAR3D_output \
    --parallel 16 \
    --label special --model-tag gpt55 \
    --max-concurrent 5    