import time


def esperar(c, job_id, limite=600):
    for _ in range(limite):
        j = c.get(f"/jobs/{job_id}").json()
        if j["status"] in ("concluido", "erro"):
            return j
        time.sleep(1)
    raise TimeoutError(job_id)
