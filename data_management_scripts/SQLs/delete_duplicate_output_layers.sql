--SELECT name, name_alt--COUNT(id), name, model, system, system_version, model_run_id --id, name, data_source_id, system, system_version, model, model_version, output_type, cma_id, model_run_id, description, name_alt, category, subcategory, data_format
	--FROM public.outputlayer
	
	UPDATE outputlayer
	SET name_alt = 'Cluster label count'
	WHERE name like '%luster_label_c%'
--GROUP BY name, model, system, system_version, model_run_id
--ORDER BY model, name


DELETE FROM outputlayer
WHERE id in (
	SELECT MAX(id)
	FROM outputlayer
	GROUP BY download_url
	HAVING COUNT(id) > 1
)