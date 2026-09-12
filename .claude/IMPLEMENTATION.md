# WP972f785f0b97 implementation boundary

Source base e813806b51fb5efaef5d5755c292f8027ce1b2eb; own branch feat/prepared-food-schema27-0909.
Root prepared-food-sql27-contract-0908.md FULLREAD; this fixes the database consumer contract before edits.

Public exact signatures:
- create_food_v27(bigint actor,bigint expected_authz,bigint original_location,jsonb payload) RETURNS jsonb {public_id:string,row_version:integer}.
- update_food_v27(bigint actor,bigint expected_authz,bigint original_location,uuid food_uuid,bigint expected_food_version,jsonb payload) RETURNS jsonb, same result.
- freeze_recipe_v27(bigint actor,bigint expected_authz,bigint original_location,uuid recipe_uuid,bigint expected_recipe_version,text expected_dependency_hash) RETURNS jsonb, same keys as freeze_recipe_revision_v22: public_id,recipe_public_id,revision_number,recipe_row_version,content_hash_sha256.
- recipe_dependency_preview_v27(bigint original_location,uuid recipe_uuid,bigint expected_recipe_version) RETURNS jsonb {recipe_public_id,recipe_row_version,complete:boolean,issues:array, snapshot:object,dependency_hash_sha256:text}. STABLE SECURITY DEFINER, fixed search_path; scoped SELECT-only body, no actor/isolation mutation/graph advisory acquisition. App service performs normal draft.read; read-only RR works.

Food payload: old core keys name/category_public_id/base_unit_code/density_g_per_ml/piece_weight_g/note, source fields on creation only as existing source contract; REQUIRED storage_location_public_ids array1..64 distinct UUID; optional paired prepared_recipe_revision_public_id + prepared_recipe_content_hash_sha256, both null = explicitly raw, either omitted pair allowed only as explicit complete save semantics defined below. Update omission preserves existing pin (legacy missing new fields cannot detach); supplying both null explicitly removes it. Unknown/partial pair rejected. Missing storage always invalid. Core + links + pin commit with one normalized no-op comparison, one row bump, one derived audit.

v2 shape:
{schema_version:2,recipe:<unchanged v1 recipe payload>,calculation:<existing>,
 units:[<root referenced units incl Food bases, sorted public UUID>],
 foods:[<legacy Food fields plus base_unit metadata,storage_locations:[{public_id,row_version,name,...}],prepared_recipe:null|{recipe_public_id,revision_public_id,content_hash_sha256}>],
 prepared_revisions:[{recipe_public_id,revision_public_id,content_hash_sha256,snapshot:<node body>}]}
Node body is immutable child snapshot with only its top-level prepared_revisions index removed for v2; v1 child body is exact stored v1. Child indices are merged/deduplicated by immutable revision UUID into the parent's sorted index. Thus each node body occurs once; nested links resolve exclusively against this index. Stored child hash remains original immutable-revision hash; reconstruct its exact original v2 index from its reachable children when whole-snapshot verification is needed. Database copies only checked stored revisions, never caller JSON. No current Food lookup for v1 historical nodes. No v1 writes/rewrites.

Preview hash is SHA256 of PostgreSQL canonical jsonb::text for all preview fields except dependency_hash_sha256; includes completeness/issues and root identity/version. Freeze recomputes same bytes under locks and compares first, rejects incomplete afterwards. Frozen revision content_hash remains SHA256(snapshot::text), distinct from preview hash. issues use bounded field/code objects, no arbitrary SQL.

Enforcement:
- Migration first locks storage references (SHARE), then Foods/links in final ACCESS EXCLUSIVE DDL mode, then reads gaps before DDL/nextval/ledger. A waiting old writer commits before that fresh check; no earlier empty snapshot is reused. Final mode avoids a SHARE-to-DDL lock upgrade while old writers wait.
- Deferred final-state constraint triggers on Foods, Food-storage and storage-active changes enforce >=1active same-site storage and prepared-yield compatibility, including privileged bad writes. No graph lock acquired in triggers.
- One private graph lock after original actor/location guard, before ordinary references/aggregate locks. All public pin saves and freeze participate. Current graph traversal separate from immutable snapshot closure, bounded before queue expansion.
- Retain unaffected v21 metadata/tags/review/active/storage verbs only under final completeness/compatibility triggers; retain update_food_v21 only if its old complete core update cannot bypass pin compatibility (trigger checks).
- Revoke create_food_v21 and freeze_recipe_revision_v22 from App; also private recipe_write_v22/master_food_mutate remain revoked. Legacy freeze/create owner use remains constrained by final invariants where applicable; direct App execution denied.
- permissions.sql repeats exact revokes after historical grant block. All new private functions revoked from PUBLIC/app/backup/auth_issuer, four public functions app-only. No table DML grants.
- Incomplete Recipe heads continue existing v22 create/update. All future v27 freeze/import admission checks nonempty/allFood/allQuantity/allUnit.
- Existing migrations byte-identical; schema27 registry/validator and necessary ledger fixtures only outside new tests. No service/UI/PDF edits.

Risks/manual SQL blast radius: HIGH (Food write/ACL, freeze, DB migration and all future recipe readers). GitNexus may not index PL/pgSQL; no LOW inference from absence. Existing Python registration/validators impacted separately before edits.
Expected migration may exceed600 lines because distinct bounded graph traversal, v2 closure, aggregate mutation and independent deferred guards are necessary; notify Root before writing an oversized migration, do not minify.

Test pool exclusively PG16 32835 / Redis32836 via worker-test-prepared-food-schema27-0909-gate.sh. Credentials only existing wrapper. No other runtime touched.
