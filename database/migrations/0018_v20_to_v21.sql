BEGIN;
SET search_path TO cafeteria, public;

-- Unicode 16.0.0: reject every category C character and markup delimiters.
CREATE FUNCTION master_text(p_value text, p_max integer, p_required boolean DEFAULT true)
RETURNS text LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v text;
BEGIN
    IF p_value IS NULL THEN
        IF p_required THEN RAISE EXCEPTION 'Missing text.' USING ERRCODE='P1901'; END IF;
        RETURN NULL;
    END IF;
    IF p_value ~ U&'[\0001-\001F\007F-\009F\00AD\0378-\0379\0380-\0383\038B\038D\03A2\0530\0557-\0558\058B-\058C\0590\05C8-\05CF\05EB-\05EE\05F5-\0605\061C\06DD\070E-\070F\074B-\074C\07B2-\07BF\07FB-\07FC\082E-\082F\083F\085C-\085D\085F\086B-\086F\088F-\0896\08E2\0984\098D-\098E\0991-\0992\09A9\09B1\09B3-\09B5\09BA-\09BB\09C5-\09C6\09C9-\09CA\09CF-\09D6\09D8-\09DB\09DE\09E4-\09E5\09FF-\0A00\0A04\0A0B-\0A0E\0A11-\0A12\0A29\0A31\0A34\0A37\0A3A-\0A3B\0A3D\0A43-\0A46\0A49-\0A4A\0A4E-\0A50\0A52-\0A58\0A5D\0A5F-\0A65\0A77-\0A80\0A84\0A8E\0A92\0AA9\0AB1\0AB4\0ABA-\0ABB\0AC6\0ACA\0ACE-\0ACF\0AD1-\0ADF\0AE4-\0AE5\0AF2-\0AF8\0B00\0B04\0B0D-\0B0E\0B11-\0B12\0B29\0B31\0B34\0B3A-\0B3B\0B45-\0B46\0B49-\0B4A\0B4E-\0B54\0B58-\0B5B\0B5E\0B64-\0B65\0B78-\0B81\0B84\0B8B-\0B8D\0B91\0B96-\0B98\0B9B\0B9D\0BA0-\0BA2\0BA5-\0BA7\0BAB-\0BAD\0BBA-\0BBD\0BC3-\0BC5\0BC9\0BCE-\0BCF\0BD1-\0BD6\0BD8-\0BE5\0BFB-\0BFF\0C0D\0C11\0C29\0C3A-\0C3B\0C45\0C49\0C4E-\0C54\0C57\0C5B-\0C5C\0C5E-\0C5F\0C64-\0C65\0C70-\0C76\0C8D\0C91\0CA9\0CB4\0CBA-\0CBB\0CC5\0CC9\0CCE-\0CD4\0CD7-\0CDC\0CDF\0CE4-\0CE5\0CF0\0CF4-\0CFF\0D0D\0D11\0D45\0D49\0D50-\0D53\0D64-\0D65\0D80\0D84\0D97-\0D99\0DB2\0DBC\0DBE-\0DBF\0DC7-\0DC9\0DCB-\0DCE\0DD5\0DD7\0DE0-\0DE5\0DF0-\0DF1\0DF5-\0E00\0E3B-\0E3E\0E5C-\0E80\0E83\0E85\0E8B\0EA4\0EA6\0EBE-\0EBF\0EC5\0EC7\0ECF\0EDA-\0EDB\0EE0-\0EFF\0F48\0F6D-\0F70\0F98\0FBD\0FCD\0FDB-\0FFF\10C6\10C8-\10CC\10CE-\10CF\1249\124E-\124F\1257\1259\125E-\125F\1289\128E-\128F\12B1\12B6-\12B7\12BF\12C1\12C6-\12C7\12D7\1311\1316-\1317\135B-\135C\137D-\137F\139A-\139F\13F6-\13F7\13FE-\13FF\169D-\169F\16F9-\16FF\1716-\171E\1737-\173F\1754-\175F\176D\1771\1774-\177F\17DE-\17DF\17EA-\17EF\17FA-\17FF\180E\181A-\181F\1879-\187F\18AB-\18AF\18F6-\18FF\191F\192C-\192F\193C-\193F\1941-\1943\196E-\196F\1975-\197F\19AC-\19AF\19CA-\19CF\19DB-\19DD\1A1C-\1A1D\1A5F\1A7D-\1A7E\1A8A-\1A8F\1A9A-\1A9F\1AAE-\1AAF\1ACF-\1AFF\1B4D\1BF4-\1BFB\1C38-\1C3A\1C4A-\1C4C\1C8B-\1C8F\1CBB-\1CBC\1CC8-\1CCF\1CFB-\1CFF\1F16-\1F17\1F1E-\1F1F\1F46-\1F47\1F4E-\1F4F\1F58\1F5A\1F5C\1F5E\1F7E-\1F7F\1FB5\1FC5\1FD4-\1FD5\1FDC\1FF0-\1FF1\1FF5\1FFF\200B-\200F\202A-\202E\2060-\206F\2072-\2073\208F\209D-\209F\20C1-\20CF\20F1-\20FF\218C-\218F\242A-\243F\244B-\245F\2B74-\2B75\2B96\2CF4-\2CF8\2D26\2D28-\2D2C\2D2E-\2D2F\2D68-\2D6E\2D71-\2D7E\2D97-\2D9F\2DA7\2DAF\2DB7\2DBF\2DC7\2DCF\2DD7\2DDF\2E5E-\2E7F\2E9A\2EF4-\2EFF\2FD6-\2FEF\3040\3097-\3098\3100-\3104\3130\318F\31E6-\31EE\321F\A48D-\A48F\A4C7-\A4CF\A62C-\A63F\A6F8-\A6FF\A7CE-\A7CF\A7D2\A7D4\A7DD-\A7F1\A82D-\A82F\A83A-\A83F\A878-\A87F\A8C6-\A8CD\A8DA-\A8DF\A954-\A95E\A97D-\A97F\A9CE\A9DA-\A9DD\A9FF\AA37-\AA3F\AA4E-\AA4F\AA5A-\AA5B\AAC3-\AADA\AAF7-\AB00\AB07-\AB08\AB0F-\AB10\AB17-\AB1F\AB27\AB2F\AB6C-\AB6F\ABEE-\ABEF\ABFA-\ABFF\D7A4-\D7AF\D7C7-\D7CA\D7FC-\F8FF\FA6E-\FA6F\FADA-\FAFF\FB07-\FB12\FB18-\FB1C\FB37\FB3D\FB3F\FB42\FB45\FBC3-\FBD2\FD90-\FD91\FDC8-\FDCE\FDD0-\FDEF\FE1A-\FE1F\FE53\FE67\FE6C-\FE6F\FE75\FEFD-\FF00\FFBF-\FFC1\FFC8-\FFC9\FFD0-\FFD1\FFD8-\FFD9\FFDD-\FFDF\FFE7\FFEF-\FFFB\FFFE-\FFFF\+01000C\+010027\+01003B\+01003E\+01004E-\+01004F\+01005E-\+01007F\+0100FB-\+0100FF\+010103-\+010106\+010134-\+010136\+01018F\+01019D-\+01019F\+0101A1-\+0101CF\+0101FE-\+01027F\+01029D-\+01029F\+0102D1-\+0102DF\+0102FC-\+0102FF\+010324-\+01032C\+01034B-\+01034F\+01037B-\+01037F\+01039E\+0103C4-\+0103C7\+0103D6-\+0103FF\+01049E-\+01049F\+0104AA-\+0104AF\+0104D4-\+0104D7\+0104FC-\+0104FF\+010528-\+01052F\+010564-\+01056E\+01057B\+01058B\+010593\+010596\+0105A2\+0105B2\+0105BA\+0105BD-\+0105BF\+0105F4-\+0105FF\+010737-\+01073F\+010756-\+01075F\+010768-\+01077F\+010786\+0107B1\+0107BB-\+0107FF\+010806-\+010807\+010809\+010836\+010839-\+01083B\+01083D-\+01083E\+010856\+01089F-\+0108A6\+0108B0-\+0108DF\+0108F3\+0108F6-\+0108FA\+01091C-\+01091E\+01093A-\+01093E\+010940-\+01097F\+0109B8-\+0109BB\+0109D0-\+0109D1\+010A04\+010A07-\+010A0B\+010A14\+010A18\+010A36-\+010A37\+010A3B-\+010A3E\+010A49-\+010A4F\+010A59-\+010A5F\+010AA0-\+010ABF\+010AE7-\+010AEA\+010AF7-\+010AFF\+010B36-\+010B38\+010B56-\+010B57\+010B73-\+010B77\+010B92-\+010B98\+010B9D-\+010BA8\+010BB0-\+010BFF\+010C49-\+010C7F\+010CB3-\+010CBF\+010CF3-\+010CF9\+010D28-\+010D2F\+010D3A-\+010D3F\+010D66-\+010D68\+010D86-\+010D8D\+010D90-\+010E5F\+010E7F\+010EAA\+010EAE-\+010EAF\+010EB2-\+010EC1\+010EC5-\+010EFB\+010F28-\+010F2F\+010F5A-\+010F6F\+010F8A-\+010FAF\+010FCC-\+010FDF\+010FF7-\+010FFF\+01104E-\+011051\+011076-\+01107E\+0110BD\+0110C3-\+0110CF\+0110E9-\+0110EF\+0110FA-\+0110FF\+011135\+011148-\+01114F\+011177-\+01117F\+0111E0\+0111F5-\+0111FF\+011212\+011242-\+01127F\+011287\+011289\+01128E\+01129E\+0112AA-\+0112AF\+0112EB-\+0112EF\+0112FA-\+0112FF\+011304\+01130D-\+01130E\+011311-\+011312\+011329\+011331\+011334\+01133A\+011345-\+011346\+011349-\+01134A\+01134E-\+01134F\+011351-\+011356\+011358-\+01135C\+011364-\+011365\+01136D-\+01136F\+011375-\+01137F\+01138A\+01138C-\+01138D\+01138F\+0113B6\+0113C1\+0113C3-\+0113C4\+0113C6\+0113CB\+0113D6\+0113D9-\+0113E0\+0113E3-\+0113FF\+01145C\+011462-\+01147F\+0114C8-\+0114CF\+0114DA-\+01157F\+0115B6-\+0115B7\+0115DE-\+0115FF\+011645-\+01164F\+01165A-\+01165F\+01166D-\+01167F\+0116BA-\+0116BF\+0116CA-\+0116CF\+0116E4-\+0116FF\+01171B-\+01171C\+01172C-\+01172F\+011747-\+0117FF\+01183C-\+01189F\+0118F3-\+0118FE\+011907-\+011908\+01190A-\+01190B\+011914\+011917\+011936\+011939-\+01193A\+011947-\+01194F\+01195A-\+01199F\+0119A8-\+0119A9\+0119D8-\+0119D9\+0119E5-\+0119FF\+011A48-\+011A4F\+011AA3-\+011AAF\+011AF9-\+011AFF\+011B0A-\+011BBF\+011BE2-\+011BEF\+011BFA-\+011BFF\+011C09\+011C37\+011C46-\+011C4F\+011C6D-\+011C6F\+011C90-\+011C91\+011CA8\+011CB7-\+011CFF\+011D07\+011D0A\+011D37-\+011D39\+011D3B\+011D3E\+011D48-\+011D4F\+011D5A-\+011D5F\+011D66\+011D69\+011D8F\+011D92\+011D99-\+011D9F\+011DAA-\+011EDF\+011EF9-\+011EFF\+011F11\+011F3B-\+011F3D\+011F5B-\+011FAF\+011FB1-\+011FBF\+011FF2-\+011FFE\+01239A-\+0123FF\+01246F\+012475-\+01247F\+012544-\+012F8F\+012FF3-\+012FFF\+013430-\+01343F\+013456-\+01345F\+0143FB-\+0143FF\+014647-\+0160FF\+01613A-\+0167FF\+016A39-\+016A3F\+016A5F\+016A6A-\+016A6D\+016ABF\+016ACA-\+016ACF\+016AEE-\+016AEF\+016AF6-\+016AFF\+016B46-\+016B4F\+016B5A\+016B62\+016B78-\+016B7C\+016B90-\+016D3F\+016D7A-\+016E3F\+016E9B-\+016EFF\+016F4B-\+016F4E\+016F88-\+016F8E\+016FA0-\+016FDF\+016FE5-\+016FEF\+016FF2-\+016FFF\+0187F8-\+0187FF\+018CD6-\+018CFE\+018D09-\+01AFEF\+01AFF4\+01AFFC\+01AFFF\+01B123-\+01B131\+01B133-\+01B14F\+01B153-\+01B154\+01B156-\+01B163\+01B168-\+01B16F\+01B2FC-\+01BBFF\+01BC6B-\+01BC6F\+01BC7D-\+01BC7F\+01BC89-\+01BC8F\+01BC9A-\+01BC9B\+01BCA0-\+01CBFF\+01CCFA-\+01CCFF\+01CEB4-\+01CEFF\+01CF2E-\+01CF2F\+01CF47-\+01CF4F\+01CFC4-\+01CFFF\+01D0F6-\+01D0FF\+01D127-\+01D128\+01D173-\+01D17A\+01D1EB-\+01D1FF\+01D246-\+01D2BF\+01D2D4-\+01D2DF\+01D2F4-\+01D2FF\+01D357-\+01D35F\+01D379-\+01D3FF\+01D455\+01D49D\+01D4A0-\+01D4A1\+01D4A3-\+01D4A4\+01D4A7-\+01D4A8\+01D4AD\+01D4BA\+01D4BC\+01D4C4\+01D506\+01D50B-\+01D50C\+01D515\+01D51D\+01D53A\+01D53F\+01D545\+01D547-\+01D549\+01D551\+01D6A6-\+01D6A7\+01D7CC-\+01D7CD\+01DA8C-\+01DA9A\+01DAA0\+01DAB0-\+01DEFF\+01DF1F-\+01DF24\+01DF2B-\+01DFFF\+01E007\+01E019-\+01E01A\+01E022\+01E025\+01E02B-\+01E02F\+01E06E-\+01E08E\+01E090-\+01E0FF\+01E12D-\+01E12F\+01E13E-\+01E13F\+01E14A-\+01E14D\+01E150-\+01E28F\+01E2AF-\+01E2BF\+01E2FA-\+01E2FE\+01E300-\+01E4CF\+01E4FA-\+01E5CF\+01E5FB-\+01E5FE\+01E600-\+01E7DF\+01E7E7\+01E7EC\+01E7EF\+01E7FF\+01E8C5-\+01E8C6\+01E8D7-\+01E8FF\+01E94C-\+01E94F\+01E95A-\+01E95D\+01E960-\+01EC70\+01ECB5-\+01ED00\+01ED3E-\+01EDFF\+01EE04\+01EE20\+01EE23\+01EE25-\+01EE26\+01EE28\+01EE33\+01EE38\+01EE3A\+01EE3C-\+01EE41\+01EE43-\+01EE46\+01EE48\+01EE4A\+01EE4C\+01EE50\+01EE53\+01EE55-\+01EE56\+01EE58\+01EE5A\+01EE5C\+01EE5E\+01EE60\+01EE63\+01EE65-\+01EE66\+01EE6B\+01EE73\+01EE78\+01EE7D\+01EE7F\+01EE8A\+01EE9C-\+01EEA0\+01EEA4\+01EEAA\+01EEBC-\+01EEEF\+01EEF2-\+01EFFF\+01F02C-\+01F02F\+01F094-\+01F09F\+01F0AF-\+01F0B0\+01F0C0\+01F0D0\+01F0F6-\+01F0FF\+01F1AE-\+01F1E5\+01F203-\+01F20F\+01F23C-\+01F23F\+01F249-\+01F24F\+01F252-\+01F25F\+01F266-\+01F2FF\+01F6D8-\+01F6DB\+01F6ED-\+01F6EF\+01F6FD-\+01F6FF\+01F777-\+01F77A\+01F7DA-\+01F7DF\+01F7EC-\+01F7EF\+01F7F1-\+01F7FF\+01F80C-\+01F80F\+01F848-\+01F84F\+01F85A-\+01F85F\+01F888-\+01F88F\+01F8AE-\+01F8AF\+01F8BC-\+01F8BF\+01F8C2-\+01F8FF\+01FA54-\+01FA5F\+01FA6E-\+01FA6F\+01FA7D-\+01FA7F\+01FA8A-\+01FA8E\+01FAC7-\+01FACD\+01FADD-\+01FADE\+01FAEA-\+01FAEF\+01FAF9-\+01FAFF\+01FB93\+01FBFA-\+01FFFF\+02A6E0-\+02A6FF\+02B73A-\+02B73F\+02B81E-\+02B81F\+02CEA2-\+02CEAF\+02EBE1-\+02EBEF\+02EE5E-\+02F7FF\+02FA1E-\+02FFFF\+03134B-\+03134F\+0323B0-\+0E00FF\+0E01F0-\+10FFFF<>]' THEN
        RAISE EXCEPTION 'Invalid text character.' USING ERRCODE='P1901';
    END IF;
    v := btrim(regexp_replace(normalize(p_value, NFC), U&'[ \00A0\1680\2000-\200A\2028\2029\202F\205F\3000]+', ' ', 'g'));
    IF length(v)>p_max OR (p_required AND v='') THEN
        RAISE EXCEPTION 'Invalid text length.' USING ERRCODE='P1901';
    END IF;
    RETURN v;
END;
$fn$;
CREATE FUNCTION master_factor(p_value numeric) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $fn$
 SELECT p_value IS NOT NULL AND p_value > 0 AND p_value < 100000000000
        AND p_value=round(p_value,9);
$fn$;
CREATE FUNCTION master_quantity(p_value numeric) RETURNS boolean
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $fn$
 SELECT p_value IS NOT NULL AND p_value > 0 AND p_value < 1000000000000
        AND p_value=round(p_value,6);
$fn$;

CREATE TABLE IF NOT EXISTS measurement_units (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    code text NOT NULL UNIQUE CHECK(code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
    display_name text NOT NULL CHECK(display_name=master_text(display_name,120)),
    dimension text NOT NULL CHECK(dimension IN ('mass','volume','count','contextual')),
    base_factor numeric,
    active boolean NOT NULL DEFAULT true,
    CHECK((dimension='contextual' AND base_factor IS NULL) OR
          (dimension<>'contextual' AND master_factor(base_factor)))
);

CREATE TABLE IF NOT EXISTS food_categories (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    location_id bigint NOT NULL REFERENCES locations(id),
    code text NOT NULL CHECK(code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
    name text NOT NULL CHECK(name=master_text(name,120)),
    sort_order smallint NOT NULL DEFAULT 1 CHECK(sort_order BETWEEN 1 AND 9999),
    active boolean NOT NULL DEFAULT true,
    UNIQUE(location_id,id), UNIQUE(location_id,code)
);

CREATE UNIQUE INDEX uq_food_categories_name ON food_categories(location_id,lower(btrim(name)));

CREATE TABLE IF NOT EXISTS tags (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    location_id bigint NOT NULL REFERENCES locations(id),
    code text NOT NULL CHECK(code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
    name text NOT NULL CHECK(name=master_text(name,120)),
    active boolean NOT NULL DEFAULT true,
    UNIQUE(location_id,id), UNIQUE(location_id,code)
);

CREATE TABLE IF NOT EXISTS storage_locations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    location_id bigint NOT NULL REFERENCES locations(id),
    code text NOT NULL CHECK(code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
    name text NOT NULL CHECK(name=master_text(name,120)),
    sort_order smallint NOT NULL DEFAULT 1 CHECK(sort_order BETWEEN 1 AND 9999),
    active boolean NOT NULL DEFAULT true,
    UNIQUE(location_id,id), UNIQUE(location_id,code)
);

CREATE TABLE IF NOT EXISTS foods (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id),
    location_id bigint NOT NULL REFERENCES locations(id),
    name text NOT NULL CHECK(name=master_text(name,120)),
    category_id bigint, base_unit_id bigint NOT NULL REFERENCES measurement_units(id),
    density_g_per_ml numeric CHECK(density_g_per_ml IS NULL OR master_factor(density_g_per_ml)),
    piece_weight_g numeric CHECK(piece_weight_g IS NULL OR master_factor(piece_weight_g)),
    note text NOT NULL DEFAULT '' CHECK(note=master_text(note,500,false)),
    active boolean NOT NULL DEFAULT true,
    allergen_review_status text NOT NULL DEFAULT 'not_checked'
        CHECK(allergen_review_status IN ('not_checked','checked')),
    source_kind text NOT NULL DEFAULT 'manual'
        CHECK(source_kind IN ('manual','url','file_import','ai_assisted','off','supplier')),
    source_reference text CHECK(source_reference=master_text(source_reference,200,false)),
    source_url text CHECK(source_url=master_text(source_url,2048,false) AND source_url ~ '^https?://'),
    source_note text CHECK(source_note=master_text(source_note,500,false)),
    fetched_at timestamptz,
    CHECK(source_kind='manual' OR (nullif(source_reference,'') IS NOT NULL AND fetched_at IS NOT NULL
        AND (nullif(source_url,'') IS NOT NULL OR nullif(source_note,'') IS NOT NULL))),
    CHECK(source_kind<>'url' OR source_url IS NOT NULL),
    UNIQUE(location_id,id),
    FOREIGN KEY(location_id,category_id) REFERENCES food_categories(location_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX uq_foods_name ON foods(location_id,lower(btrim(name)));

CREATE TABLE IF NOT EXISTS food_tags (
    location_id bigint NOT NULL, food_id bigint NOT NULL, tag_id bigint NOT NULL,
    PRIMARY KEY(food_id,tag_id),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(location_id,tag_id) REFERENCES tags(location_id,id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS food_storage_locations (
    location_id bigint NOT NULL, food_id bigint NOT NULL, storage_location_id bigint NOT NULL,
    PRIMARY KEY(food_id,storage_location_id),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(location_id,storage_location_id) REFERENCES storage_locations(location_id,id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS food_labels (
    location_id bigint NOT NULL, food_id bigint NOT NULL,
    label_id smallint NOT NULL REFERENCES dietary_labels(id) ON DELETE RESTRICT,
    PRIMARY KEY(food_id,label_id),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS food_allergens (
    location_id bigint NOT NULL, food_id bigint NOT NULL,
    allergen_id smallint NOT NULL REFERENCES allergens(id) ON DELETE RESTRICT,
    presence text NOT NULL CHECK(presence IN ('contains','may_contain')),
    PRIMARY KEY(food_id,allergen_id),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT
);

CREATE FUNCTION master_json_valid(p_value jsonb, p_depth integer DEFAULT 0)
RETURNS boolean LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v jsonb; n integer;
BEGIN
    IF p_value IS NULL OR p_depth>5 THEN RETURN false; END IF;
    IF p_depth=0 THEN
        SELECT count(*) INTO n FROM jsonb_path_query(p_value,'strict $.**') node
          CROSS JOIN LATERAL jsonb_object_keys(
            CASE WHEN jsonb_typeof(node)='object' THEN node ELSE '{}'::jsonb END) k;
        IF n>200 THEN RETURN false; END IF;
    END IF;
    IF jsonb_typeof(p_value)='object' THEN
        SELECT count(*) INTO n FROM jsonb_object_keys(p_value);
        IF n>200 THEN RETURN false; END IF;
        FOR v IN SELECT value FROM jsonb_each(p_value) LOOP
            IF NOT master_json_valid(v,p_depth+1) THEN RETURN false; END IF;
        END LOOP;
    ELSIF jsonb_typeof(p_value)='array' THEN
        FOR v IN SELECT value FROM jsonb_array_elements(p_value) LOOP
            IF NOT master_json_valid(v,p_depth+1) THEN RETURN false; END IF;
        END LOOP;
    END IF;
    RETURN true;
END;
$fn$;

CREATE TABLE IF NOT EXISTS food_data_proposals (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    row_version bigint NOT NULL DEFAULT 1 CHECK(row_version>0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_by bigint REFERENCES users(id), updated_by bigint REFERENCES users(id), location_id bigint NOT NULL REFERENCES locations(id), food_id bigint,
    source text NOT NULL CHECK(source IN ('off','supplier','ai','file_import')),
    source_reference text NOT NULL CHECK(source_reference=master_text(source_reference,200)),
    source_url text CHECK(source_url=master_text(source_url,2048,false) AND source_url ~ '^https?://'),
    source_note text CHECK(source_note=master_text(source_note,500,false)),
    fetched_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object' AND
        octet_length(payload::text)<=65536 AND master_json_valid(payload)),
    status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','accepted','rejected')),
    decided_by bigint REFERENCES users(id), decided_at timestamptz,
    decision_detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK((status='open' AND decided_by IS NULL AND decided_at IS NULL AND decision_detail='{}')
       OR (status<>'open' AND decided_by IS NOT NULL AND decided_at IS NOT NULL)),
    FOREIGN KEY(location_id,food_id) REFERENCES foods(location_id,id) ON DELETE RESTRICT
);

CREATE FUNCTION protect_master_data() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'Archive instead of deleting master data.' USING ERRCODE='55000';
    END IF;
    IF NEW.id<>OLD.id OR NEW.public_id<>OLD.public_id OR NEW.created_at<>OLD.created_at
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR to_jsonb(NEW)->'location_id' IS DISTINCT FROM to_jsonb(OLD)->'location_id'
       OR to_jsonb(NEW)->'code' IS DISTINCT FROM to_jsonb(OLD)->'code' THEN
        RAISE EXCEPTION 'Immutable master identity.' USING ERRCODE='55000';
    END IF;
    IF TG_TABLE_NAME='measurement_units' THEN
        IF NEW.dimension<>OLD.dimension OR NEW.base_factor IS DISTINCT FROM OLD.base_factor
            OR (OLD.code IN ('G','ML','STK') AND NOT NEW.active) THEN
            RAISE EXCEPTION 'Immutable unit semantics.' USING ERRCODE='55000';
        END IF;
    ELSIF TG_TABLE_NAME='foods' THEN
        IF (to_jsonb(NEW)-ARRAY['name','category_id','base_unit_id','density_g_per_ml','piece_weight_g',
            'note','active','allergen_review_status','updated_at','updated_by','row_version'])
            IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['name','category_id','base_unit_id','density_g_per_ml',
            'piece_weight_g','note','active','allergen_review_status','updated_at','updated_by','row_version']) THEN
            RAISE EXCEPTION 'Immutable food origin.' USING ERRCODE='55000';
        END IF;
    END IF;
    RETURN NEW;
END;
$fn$;
CREATE FUNCTION protect_food_proposal() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'Proposal cannot be deleted.' USING ERRCODE='55000';
    END IF;
    IF OLD.status<>'open' OR NEW.status NOT IN ('accepted','rejected') OR
       (to_jsonb(NEW)-ARRAY['food_id','status','decided_by','decided_at','decision_detail','row_version','updated_at','updated_by'])
       IS DISTINCT FROM
       (to_jsonb(OLD)-ARRAY['food_id','status','decided_by','decided_at','decision_detail','row_version','updated_at','updated_by']) OR
       (NEW.food_id IS DISTINCT FROM OLD.food_id AND NOT
         (OLD.food_id IS NULL AND NEW.food_id IS NOT NULL AND NEW.status='accepted')) OR
       (NEW.status='accepted' AND NEW.food_id IS NULL) THEN
        RAISE EXCEPTION 'Immutable proposal source or decision.' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END;
$fn$;

CREATE TRIGGER trg_measurement_units_identity BEFORE UPDATE OR DELETE ON measurement_units
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_measurement_units_no_truncate BEFORE TRUNCATE ON measurement_units
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_measurement_units_version BEFORE UPDATE ON measurement_units
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_food_categories_identity BEFORE UPDATE OR DELETE ON food_categories
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_food_categories_no_truncate BEFORE TRUNCATE ON food_categories
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_food_categories_version BEFORE UPDATE ON food_categories
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_tags_identity BEFORE UPDATE OR DELETE ON tags
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_tags_no_truncate BEFORE TRUNCATE ON tags
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_tags_version BEFORE UPDATE ON tags
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_storage_locations_identity BEFORE UPDATE OR DELETE ON storage_locations
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_storage_locations_no_truncate BEFORE TRUNCATE ON storage_locations
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_storage_locations_version BEFORE UPDATE ON storage_locations
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_foods_identity BEFORE UPDATE OR DELETE ON foods
FOR EACH ROW EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_foods_no_truncate BEFORE TRUNCATE ON foods
FOR EACH STATEMENT EXECUTE FUNCTION protect_master_data();
CREATE TRIGGER trg_foods_version BEFORE UPDATE ON foods
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

CREATE TRIGGER trg_food_data_proposals_identity BEFORE UPDATE OR DELETE ON food_data_proposals
FOR EACH ROW EXECUTE FUNCTION protect_food_proposal();
CREATE TRIGGER trg_food_data_proposals_no_truncate BEFORE TRUNCATE ON food_data_proposals
FOR EACH STATEMENT EXECUTE FUNCTION protect_food_proposal();
CREATE TRIGGER trg_food_data_proposals_version BEFORE UPDATE ON food_data_proposals
FOR EACH ROW EXECUTE FUNCTION bump_row_version_and_updated_at();

INSERT INTO measurement_units(code,display_name,dimension,base_factor) VALUES
 ('G','Gramm','mass',1),('KG','Kilogramm','mass',1000),('ML','Milliliter','volume',1),
 ('L','Liter','volume',1000),('EL','Esslöffel (15 ml)','volume',15),
 ('TL','Teelöffel (5 ml)','volume',5),('STK','Stück','count',1),
 ('PORTION','Portion','contextual',NULL),('PRISE','Prise','contextual',NULL);

CREATE FUNCTION require_master_data_actor(p_actor bigint,p_version bigint,p_capability text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v users%ROWTYPE;
BEGIN
    IF current_setting('transaction_isolation')<>'read committed' OR p_actor IS NULL OR p_actor<=0
       OR p_version IS NULL OR p_version<=0 THEN
        RAISE EXCEPTION 'Invalid actor expectation or isolation.' USING ERRCODE='P1901';
    END IF;
    PERFORM set_config('lock_timeout','5s',true);
    PERFORM role_code FROM application_roles ORDER BY role_code FOR SHARE;
    SELECT * INTO v FROM users WHERE id=p_actor FOR SHARE;
    IF NOT FOUND OR v.disabled_at IS NOT NULL THEN
        RAISE EXCEPTION 'Active actor required.' USING ERRCODE='P1902';
    END IF;
    IF v.authz_version<>p_version THEN
        RAISE EXCEPTION 'Stale actor.' USING ERRCODE='P1903';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM user_role_cache r JOIN application_roles a USING(role_code)
        WHERE r.user_id=p_actor AND a.active AND (r.role_code='Cafeteria.Admin' OR
          (p_capability IN ('masterdata.write','recipe.write') AND
            r.role_code IN ('Cafeteria.Editor','Cafeteria.Publisher')) OR
          (p_capability='recipe.import' AND r.role_code='Cafeteria.Publisher'))) THEN
        RAISE EXCEPTION 'Capability denied.' USING ERRCODE='P1902';
    END IF;
END;
$fn$;
CREATE FUNCTION master_location(p_location bigint) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF NOT lock_expected_active_location(p_location) THEN
        RAISE EXCEPTION 'Master data location unavailable.' USING ERRCODE='P1901', DETAIL='master_location';
    END IF;
END;
$fn$;
CREATE FUNCTION master_audit(p_actor bigint,p_version bigint,p_location bigint,p_kind text,
    p_target uuid,p_action text,p_before bigint,p_after bigint,p_details jsonb DEFAULT '{}'::jsonb)
RETURNS void LANGUAGE sql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 INSERT INTO audit_events(actor_user_id,action,entity_type,entity_public_id,details)
 VALUES(p_actor,'masterdata.'||p_action,p_kind,p_target,jsonb_build_object(
    'actor_authz_version',p_version,'location_id',p_location,'action',p_action,
    'row_version_before',p_before,'row_version_after',p_after)||p_details);
$fn$;

CREATE FUNCTION master_payload(p_payload jsonb,p_keys text[]) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF p_payload IS NULL OR jsonb_typeof(p_payload)<>'object' OR
       EXISTS(SELECT 1 FROM jsonb_object_keys(p_payload) k WHERE NOT k=ANY(p_keys)) THEN
        RAISE EXCEPTION 'Invalid command fields.' USING ERRCODE='P1901';
    END IF;
END;
$fn$;
CREATE FUNCTION master_expectation(p_target uuid,p_version bigint) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF p_target IS NULL OR p_version IS NULL OR p_version<=0 THEN
        RAISE EXCEPTION 'Invalid object expectation.' USING ERRCODE='P1901';
    END IF;
END;
$fn$;

CREATE FUNCTION master_food_category_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v food_categories%ROWTYPE; n text; s smallint; a boolean; old_version bigint; affected bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action='create' THEN
        PERFORM master_payload(p_payload,ARRAY['code','name','sort_order']);
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL OR
           p_payload->>'code' IS NULL OR NOT (p_payload->>'code' ~ '^[A-Z][A-Z0-9_]{0,15}$') THEN
            RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901';
        END IF;
        INSERT INTO food_categories(location_id,code,name,created_by,updated_by,sort_order)
        VALUES(p_location,p_payload->>'code',master_text(p_payload->>'name',120),p_actor,p_actor
            ,COALESCE((p_payload->>'sort_order')::smallint,1)) RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM food_categories WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN
            RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000',DETAIL='stale_object';
        END IF;
        old_version:=v.row_version;
        IF p_action='update' THEN
            PERFORM master_payload(p_payload,ARRAY['name','sort_order']);
            n:=master_text(p_payload->>'name',120);
            s:=COALESCE((p_payload->>'sort_order')::smallint,v.sort_order);
            IF n=v.name AND s=v.sort_order THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            UPDATE food_categories SET name=n,updated_by=p_actor,sort_order=s
             WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action='active' THEN
            PERFORM master_payload(p_payload,ARRAY['active']);
            IF jsonb_typeof(p_payload->'active') IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid active state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>'active')::boolean;
            IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
            UPDATE food_categories SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food_category',v.public_id,p_action,old_version,v.row_version,
        jsonb_build_object('fields',p_payload-'code'));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid vocabulary data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_food_category_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_category_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION update_food_category_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_category_mutate('update',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_active_food_category_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_category_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION master_tag_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v tags%ROWTYPE; n text; s smallint; a boolean; old_version bigint; affected bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action='create' THEN
        PERFORM master_payload(p_payload,ARRAY['code','name']);
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL OR
           p_payload->>'code' IS NULL OR NOT (p_payload->>'code' ~ '^[A-Z][A-Z0-9_]{0,15}$') THEN
            RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901';
        END IF;
        INSERT INTO tags(location_id,code,name,created_by,updated_by)
        VALUES(p_location,p_payload->>'code',master_text(p_payload->>'name',120),p_actor,p_actor
            ) RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM tags WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN
            RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000',DETAIL='stale_object';
        END IF;
        old_version:=v.row_version;
        IF p_action='update' THEN
            PERFORM master_payload(p_payload,ARRAY['name']);
            n:=master_text(p_payload->>'name',120);
            IF n=v.name  THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            UPDATE tags SET name=n,updated_by=p_actor
             WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action='active' THEN
            PERFORM master_payload(p_payload,ARRAY['active']);
            IF jsonb_typeof(p_payload->'active') IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid active state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>'active')::boolean;
            IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
            UPDATE tags SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'tag',v.public_id,p_action,old_version,v.row_version,
        jsonb_build_object('fields',p_payload-'code'));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid vocabulary data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_tag_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_tag_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION update_tag_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_tag_mutate('update',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_active_tag_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_tag_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION master_storage_location_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v storage_locations%ROWTYPE; n text; s smallint; a boolean; old_version bigint; affected bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action='create' THEN
        PERFORM master_payload(p_payload,ARRAY['code','name','sort_order']);
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL OR
           p_payload->>'code' IS NULL OR NOT (p_payload->>'code' ~ '^[A-Z][A-Z0-9_]{0,15}$') THEN
            RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901';
        END IF;
        INSERT INTO storage_locations(location_id,code,name,created_by,updated_by,sort_order)
        VALUES(p_location,p_payload->>'code',master_text(p_payload->>'name',120),p_actor,p_actor
            ,COALESCE((p_payload->>'sort_order')::smallint,1)) RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM storage_locations WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown object.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN
            RAISE EXCEPTION 'Stale object.' USING ERRCODE='55000',DETAIL='stale_object';
        END IF;
        old_version:=v.row_version;
        IF p_action='update' THEN
            PERFORM master_payload(p_payload,ARRAY['name','sort_order']);
            n:=master_text(p_payload->>'name',120);
            s:=COALESCE((p_payload->>'sort_order')::smallint,v.sort_order);
            IF n=v.name AND s=v.sort_order THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            UPDATE storage_locations SET name=n,updated_by=p_actor,sort_order=s
             WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action='active' THEN
            PERFORM master_payload(p_payload,ARRAY['active']);
            IF jsonb_typeof(p_payload->'active') IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid active state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>'active')::boolean;
            IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
            IF NOT a THEN
                SELECT count(*) INTO affected FROM food_storage_locations WHERE storage_location_id=v.id;
                IF affected>0 THEN
                    RAISE EXCEPTION 'Storage location still assigned.' USING ERRCODE='55000',
                        DETAIL='storage_assignments:'||affected::text;
                END IF;
            END IF;
            UPDATE storage_locations SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'storage_location',v.public_id,p_action,old_version,v.row_version,
        jsonb_build_object('fields',p_payload-'code'));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid vocabulary data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_storage_location_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_storage_location_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION update_storage_location_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_storage_location_mutate('update',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_active_storage_location_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_storage_location_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION master_unit_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v measurement_units%ROWTYPE; n text; a boolean; old_version bigint;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action='create' THEN
        PERFORM master_payload(p_payload,ARRAY['code','display_name','dimension','base_factor']);
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL THEN
            RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901';
        END IF;
        INSERT INTO measurement_units(code,display_name,dimension,base_factor,created_by,updated_by)
        VALUES(p_payload->>'code',master_text(p_payload->>'display_name',120),p_payload->>'dimension',
            (p_payload->>'base_factor')::numeric,p_actor,p_actor) RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM measurement_units WHERE public_id=p_target FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown unit.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN
            RAISE EXCEPTION 'Stale unit.' USING ERRCODE='55000',DETAIL='stale_object';
        END IF;
        old_version:=v.row_version;
        IF p_action='rename' THEN
            PERFORM master_payload(p_payload,ARRAY['display_name']);
            n:=master_text(p_payload->>'display_name',120);
            IF n=v.display_name THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            UPDATE measurement_units SET display_name=n,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action='active' THEN
            PERFORM master_payload(p_payload,ARRAY['active']);
            IF jsonb_typeof(p_payload->'active') IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid active state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>'active')::boolean;
            IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
            UPDATE measurement_units SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
        ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'measurement_unit',v.public_id,p_action,old_version,
        v.row_version,jsonb_build_object('fields',p_payload));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid unit data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_unit_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_unit_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION rename_unit_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_unit_mutate('rename',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_active_unit_v21(p_actor bigint,p_actor_version bigint,p_location bigint,p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_unit_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION master_lock_food_refs(p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE result jsonb:='{}'; v record; ids bigint[]:='{}'; item jsonb; codes text[]; found_count integer;
BEGIN
    IF p_payload ? 'base_unit_code' THEN
        SELECT id,active INTO v FROM measurement_units WHERE code=p_payload->>'base_unit_code' FOR SHARE;
        IF NOT FOUND OR NOT v.active THEN RAISE EXCEPTION 'Unknown active unit.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('base_unit_id',v.id);
    END IF;
    IF nullif(p_payload->>'category_public_id','') IS NOT NULL OR p_payload ? 'category_code' THEN
        SELECT id,active INTO v FROM food_categories WHERE location_id=(p_payload->>'location_id')::bigint
         AND ((p_payload ? 'category_code' AND code=p_payload->>'category_code') OR
              (NOT p_payload ? 'category_code' AND public_id=(p_payload->>'category_public_id')::uuid)) FOR SHARE;
        IF NOT FOUND OR NOT v.active THEN RAISE EXCEPTION 'Unknown active category.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('category_id',v.id);
    END IF;
    IF p_payload ? 'tags' THEN
        IF jsonb_typeof(p_payload->'tags')<>'array' OR jsonb_array_length(p_payload->'tags')>64 THEN
            RAISE EXCEPTION 'Invalid tags.' USING ERRCODE='P1901';
        END IF;
        ids:='{}';
        FOR v IN SELECT id,active FROM tags WHERE location_id=(p_payload->>'location_id')::bigint
          AND public_id IN (SELECT value::uuid FROM jsonb_array_elements_text(p_payload->'tags'))
          ORDER BY id FOR SHARE LOOP
            IF NOT v.active THEN RAISE EXCEPTION 'Archived tag.' USING ERRCODE='P1901'; END IF;
            ids:=array_append(ids,v.id);
        END LOOP;
        SELECT count(DISTINCT value) INTO found_count FROM jsonb_array_elements_text(p_payload->'tags');
        IF cardinality(ids)<>found_count THEN RAISE EXCEPTION 'Unknown tag.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('tags',ids);
    END IF;
    IF p_payload ? 'storage_locations' THEN
        IF jsonb_typeof(p_payload->'storage_locations')<>'array' OR jsonb_array_length(p_payload->'storage_locations')>64 THEN
            RAISE EXCEPTION 'Invalid storage locations.' USING ERRCODE='P1901';
        END IF;
        ids:='{}';
        FOR v IN SELECT id,active FROM storage_locations WHERE location_id=(p_payload->>'location_id')::bigint
          AND public_id IN (SELECT value::uuid FROM jsonb_array_elements_text(p_payload->'storage_locations'))
          ORDER BY id FOR SHARE LOOP
            IF NOT v.active THEN RAISE EXCEPTION 'Archived storage location.' USING ERRCODE='P1901'; END IF;
            ids:=array_append(ids,v.id);
        END LOOP;
        SELECT count(DISTINCT value) INTO found_count FROM jsonb_array_elements_text(p_payload->'storage_locations');
        IF cardinality(ids)<>found_count THEN RAISE EXCEPTION 'Unknown storage location.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('storage_locations',ids);
    END IF;
    IF p_payload ? 'allergens' THEN
        IF jsonb_typeof(p_payload->'allergens')<>'array' OR jsonb_array_length(p_payload->'allergens')>64 THEN
            RAISE EXCEPTION 'Invalid allergens.' USING ERRCODE='P1901';
        END IF;
        FOR item IN SELECT value FROM jsonb_array_elements(p_payload->'allergens') LOOP
            PERFORM master_payload(item,ARRAY['code','presence']);
            IF item->>'code' IS NULL OR item->>'presence' IS NULL OR
               item->>'presence' NOT IN ('contains','may_contain') THEN
                RAISE EXCEPTION 'Invalid allergen declaration.' USING ERRCODE='P1901';
            END IF;
        END LOOP;
        IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_payload->'allergens') x
                  GROUP BY x->>'code' HAVING count(DISTINCT x->>'presence')>1) THEN
            RAISE EXCEPTION 'Conflicting allergen presence.' USING ERRCODE='P1901';
        END IF;
        SELECT array_agg(DISTINCT x->>'code') INTO codes FROM jsonb_array_elements(p_payload->'allergens') x;
        ids:='{}';
        FOR v IN SELECT id,active FROM allergens WHERE code=ANY(codes) ORDER BY id FOR SHARE LOOP
            IF NOT v.active THEN RAISE EXCEPTION 'Archived allergen.' USING ERRCODE='P1901'; END IF;
            ids:=array_append(ids,v.id);
        END LOOP;
        IF cardinality(ids)<>COALESCE(cardinality(codes),0) THEN RAISE EXCEPTION 'Unknown allergen.' USING ERRCODE='P1901'; END IF;
        SELECT COALESCE(jsonb_agg(jsonb_build_object('id',a.id,'presence',x->>'presence') ORDER BY a.id),'[]')
          INTO item FROM (SELECT DISTINCT value AS x FROM jsonb_array_elements(p_payload->'allergens')) pairs
          JOIN allergens a ON a.code=x->>'code';
        result:=result||jsonb_build_object('allergens',item);
    END IF;
    IF p_payload ? 'labels' THEN
        IF jsonb_typeof(p_payload->'labels')<>'array' OR jsonb_array_length(p_payload->'labels')>64 THEN
            RAISE EXCEPTION 'Invalid labels.' USING ERRCODE='P1901';
        END IF;
        SELECT array_agg(DISTINCT value) INTO codes FROM jsonb_array_elements_text(p_payload->'labels');
        ids:='{}';
        FOR v IN SELECT id,active FROM dietary_labels WHERE code=ANY(codes) ORDER BY id FOR SHARE LOOP
            IF NOT v.active THEN RAISE EXCEPTION 'Archived label.' USING ERRCODE='P1901'; END IF;
            ids:=array_append(ids,v.id);
        END LOOP;
        IF cardinality(ids)<>COALESCE(cardinality(codes),0) THEN RAISE EXCEPTION 'Unknown label.' USING ERRCODE='P1901'; END IF;
        result:=result||jsonb_build_object('labels',ids);
    END IF;
    RETURN result;
END;
$fn$;
CREATE FUNCTION master_food_links(p_id bigint) RETURNS jsonb
LANGUAGE sql STABLE SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT jsonb_build_object(
  'tags',COALESCE((SELECT jsonb_agg(tag_id ORDER BY tag_id) FROM food_tags WHERE food_id=p_id),'[]'),
  'storage_locations',COALESCE((SELECT jsonb_agg(storage_location_id ORDER BY storage_location_id)
      FROM food_storage_locations WHERE food_id=p_id),'[]'),
  'labels',COALESCE((SELECT jsonb_agg(label_id ORDER BY label_id) FROM food_labels WHERE food_id=p_id),'[]'),
  'allergens',COALESCE((SELECT jsonb_agg(jsonb_build_object('id',allergen_id,'presence',presence) ORDER BY allergen_id)
      FROM food_allergens WHERE food_id=p_id),'[]'));
$fn$;
CREATE FUNCTION master_replace_food_links(p_id bigint,p_location bigint,p_links jsonb) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
BEGIN
    IF p_links ? 'tags' THEN
        DELETE FROM food_tags WHERE food_id=p_id;
        INSERT INTO food_tags(location_id,food_id,tag_id)
          SELECT p_location,p_id,value::bigint FROM jsonb_array_elements_text(p_links->'tags') ORDER BY value::bigint;
    END IF;
    IF p_links ? 'storage_locations' THEN
        DELETE FROM food_storage_locations WHERE food_id=p_id;
        INSERT INTO food_storage_locations(location_id,food_id,storage_location_id)
          SELECT p_location,p_id,value::bigint FROM jsonb_array_elements_text(p_links->'storage_locations') ORDER BY value::bigint;
    END IF;
    IF p_links ? 'allergens' THEN
        DELETE FROM food_allergens WHERE food_id=p_id;
        INSERT INTO food_allergens(location_id,food_id,allergen_id,presence)
          SELECT p_location,p_id,(value->>'id')::smallint,value->>'presence'
          FROM jsonb_array_elements(p_links->'allergens') ORDER BY (value->>'id')::smallint;
    END IF;
    IF p_links ? 'labels' THEN
        DELETE FROM food_labels WHERE food_id=p_id;
        INSERT INTO food_labels(location_id,food_id,label_id)
          SELECT p_location,p_id,value::smallint FROM jsonb_array_elements_text(p_links->'labels') ORDER BY value::smallint;
    END IF;
END;
$fn$;
CREATE FUNCTION master_food_mutate(p_action text,p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v foods%ROWTYPE; previous foods%ROWTYPE; refs jsonb; links jsonb; old_version bigint; a boolean; review text;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    IF p_action IN ('create','update') THEN
        PERFORM master_payload(p_payload,ARRAY['name','category_public_id','base_unit_code',
           'density_g_per_ml','piece_weight_g','note','source_kind','source_reference','source_url','source_note','fetched_at']);
        IF p_action='update' AND p_payload ?| ARRAY['source_kind','source_reference','source_url','source_note','fetched_at'] THEN
            RAISE EXCEPTION 'Origin is immutable.' USING ERRCODE='P1901';
        END IF;
        IF p_payload->>'base_unit_code' IS NULL THEN RAISE EXCEPTION 'Unit required.' USING ERRCODE='P1901'; END IF;
    ELSIF p_action='metadata' THEN
        PERFORM master_payload(p_payload,ARRAY['allergens','labels']);
        IF NOT p_payload ?& ARRAY['allergens','labels'] THEN RAISE EXCEPTION 'Metadata required.' USING ERRCODE='P1901'; END IF;
    ELSIF p_action='tags' THEN PERFORM master_payload(p_payload,ARRAY['tags']);
    ELSIF p_action='storage_locations' THEN PERFORM master_payload(p_payload,ARRAY['storage_locations']);
    ELSIF p_action='review' THEN PERFORM master_payload(p_payload,ARRAY['checked']);
    ELSIF p_action='active' THEN PERFORM master_payload(p_payload,ARRAY['active']);
    ELSE RAISE EXCEPTION 'Invalid action.' USING ERRCODE='P1901';
    END IF;
    refs:=master_lock_food_refs(p_payload||jsonb_build_object('location_id',p_location));
    IF p_action='create' THEN
        IF p_target IS NOT NULL OR p_target_version IS NOT NULL THEN RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901'; END IF;
        INSERT INTO foods(location_id,name,category_id,base_unit_id,density_g_per_ml,piece_weight_g,note,
            source_kind,source_reference,source_url,source_note,fetched_at,created_by,updated_by)
        VALUES(p_location,master_text(p_payload->>'name',120),(refs->>'category_id')::bigint,
            (refs->>'base_unit_id')::bigint,(p_payload->>'density_g_per_ml')::numeric,(p_payload->>'piece_weight_g')::numeric,
            master_text(COALESCE(p_payload->>'note',''),500,false),COALESCE(p_payload->>'source_kind','manual'),
            master_text(p_payload->>'source_reference',200,false),master_text(p_payload->>'source_url',2048,false),
            master_text(p_payload->>'source_note',500,false),(p_payload->>'fetched_at')::timestamptz,p_actor,p_actor)
        RETURNING * INTO v;
    ELSE
        PERFORM master_expectation(p_target,p_target_version);
        SELECT * INTO v FROM foods WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown food.' USING ERRCODE='22023'; END IF;
        IF v.row_version<>p_target_version THEN RAISE EXCEPTION 'Stale food.' USING ERRCODE='55000',DETAIL='stale_object'; END IF;
        previous:=v; old_version:=v.row_version;
        IF p_action='update' THEN
            v.name:=master_text(p_payload->>'name',120); v.category_id:=(refs->>'category_id')::bigint;
            v.base_unit_id:=(refs->>'base_unit_id')::bigint;
            v.density_g_per_ml:=(p_payload->>'density_g_per_ml')::numeric;
            v.piece_weight_g:=(p_payload->>'piece_weight_g')::numeric;
            v.note:=master_text(COALESCE(p_payload->>'note',''),500,false);
            IF v IS NOT DISTINCT FROM previous THEN RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version); END IF;
            UPDATE foods SET name=v.name,category_id=v.category_id,base_unit_id=v.base_unit_id,
              density_g_per_ml=v.density_g_per_ml,piece_weight_g=v.piece_weight_g,note=v.note,updated_by=p_actor
              WHERE id=v.id RETURNING * INTO v;
        ELSIF p_action IN ('metadata','tags','storage_locations') THEN
            IF p_action<>'metadata' AND NOT refs ? p_action THEN RAISE EXCEPTION 'Missing assignments.' USING ERRCODE='P1901'; END IF;
            links:=master_food_links(v.id);
            IF NOT EXISTS(SELECT 1 FROM jsonb_each(refs) e WHERE e.value IS DISTINCT FROM links->e.key) THEN
                RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
            END IF;
            review:=CASE WHEN refs ? 'allergens' AND refs->'allergens' IS DISTINCT FROM links->'allergens'
              THEN 'not_checked' ELSE v.allergen_review_status END;
            PERFORM master_replace_food_links(v.id,p_location,refs);
            UPDATE foods SET updated_by=p_actor,allergen_review_status=review WHERE id=v.id RETURNING * INTO v;
        ELSE
            IF jsonb_typeof(p_payload->CASE WHEN p_action='review' THEN 'checked' ELSE 'active' END) IS DISTINCT FROM 'boolean' THEN
                RAISE EXCEPTION 'Invalid state.' USING ERRCODE='P1901';
            END IF;
            a:=(p_payload->>CASE WHEN p_action='review' THEN 'checked' ELSE 'active' END)::boolean;
            IF p_action='active' THEN
                IF a=v.active THEN RAISE EXCEPTION 'State already set.' USING ERRCODE='55000'; END IF;
                UPDATE foods SET active=a,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
            ELSE
                review:=CASE WHEN a THEN 'checked' ELSE 'not_checked' END;
                IF review=v.allergen_review_status THEN
                    RAISE EXCEPTION 'State already set.' USING ERRCODE='55000';
                END IF;
                UPDATE foods SET allergen_review_status=review,updated_by=p_actor WHERE id=v.id RETURNING * INTO v;
            END IF;
        END IF;
    END IF;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food',v.public_id,p_action,old_version,v.row_version,
        jsonb_build_object('fields',p_payload));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation OR invalid_datetime_format THEN
    RAISE EXCEPTION 'Invalid food data.' USING ERRCODE='P1901';
END;
$fn$;

CREATE FUNCTION create_food_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('create',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION update_food_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('update',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_food_active_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('active',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION replace_food_tags_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('tags',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION replace_food_metadata_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('metadata',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION set_food_allergen_review_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('review',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION replace_food_storage_locations_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
 SELECT master_food_mutate('storage_locations',p_actor,p_actor_version,p_location,p_target,p_target_version,p_payload);
$fn$;

CREATE FUNCTION create_proposal_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE food bigint; v food_data_proposals%ROWTYPE;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'masterdata.write');
    PERFORM master_location(p_location);
    PERFORM master_payload(p_payload,ARRAY['source','source_reference','source_url','source_note','fetched_at','payload','food_public_id']);
    IF p_target IS NOT NULL OR p_target_version IS NOT NULL THEN RAISE EXCEPTION 'Invalid creation.' USING ERRCODE='P1901'; END IF;
    IF p_payload->>'food_public_id' IS NOT NULL THEN
        SELECT id INTO food FROM foods WHERE public_id=(p_payload->>'food_public_id')::uuid
         AND location_id=p_location FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'Unknown food.' USING ERRCODE='22023'; END IF;
    END IF;
    INSERT INTO food_data_proposals(location_id,food_id,source,source_reference,source_url,source_note,
        fetched_at,payload,created_by,updated_by)
    VALUES(p_location,food,p_payload->>'source',master_text(p_payload->>'source_reference',200),
        master_text(p_payload->>'source_url',2048,false),master_text(p_payload->>'source_note',500,false),
        (p_payload->>'fetched_at')::timestamptz,p_payload->'payload',p_actor,p_actor) RETURNING * INTO v;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food_proposal',v.public_id,'create',NULL,v.row_version,
        jsonb_build_object('source',v.source,'source_reference',v.source_reference));
    RETURN jsonb_build_object('public_id',v.public_id,'row_version',v.row_version);
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation OR invalid_datetime_format THEN
    RAISE EXCEPTION 'Invalid proposal data.' USING ERRCODE='P1901';
END;
$fn$;
CREATE FUNCTION accept_proposal_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v food_data_proposals%ROWTYPE; original food_data_proposals%ROWTYPE; f foods%ROWTYPE;
    before_version bigint; refs jsonb; selected jsonb:='{}'; links jsonb; merged jsonb;
    field text; item jsonb; current_item jsonb; adopted text[]:='{}'; unchanged text[]:='{}';
    unsupported text[]; fields text[]; value numeric; category bigint; changed boolean:=false;
    decision jsonb; stamp timestamptz;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'recipe.import');
    PERFORM master_location(p_location);
    PERFORM master_expectation(p_target,p_target_version);
    PERFORM master_payload(p_payload,ARRAY['food_public_id','food_row_version','fields']);
    IF jsonb_typeof(p_payload->'fields') IS DISTINCT FROM 'array' OR
       jsonb_array_length(p_payload->'fields') NOT BETWEEN 1 AND 64 THEN
        RAISE EXCEPTION 'Select proposal fields.' USING ERRCODE='P1901';
    END IF;
    SELECT array_agg(DISTINCT x ORDER BY x) INTO fields FROM jsonb_array_elements_text(p_payload->'fields') x;
    IF EXISTS(SELECT 1 FROM unnest(fields) x WHERE x IS NULL OR
      x NOT IN ('density_g_per_ml','piece_weight_g','category_code','allergens','labels')) THEN
        RAISE EXCEPTION 'Unsupported selection.' USING ERRCODE='P1901';
    END IF;
    SELECT * INTO original FROM food_data_proposals WHERE public_id=p_target AND location_id=p_location;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unknown proposal.' USING ERRCODE='22023'; END IF;
    FOREACH field IN ARRAY fields LOOP
        IF NOT original.payload ? field THEN RAISE EXCEPTION 'Missing proposal field.' USING ERRCODE='P1901'; END IF;
        selected:=selected||jsonb_build_object(field,original.payload->field);
    END LOOP;
    refs:=master_lock_food_refs(selected||jsonb_build_object('location_id',p_location));
    PERFORM master_expectation((p_payload->>'food_public_id')::uuid,(p_payload->>'food_row_version')::bigint);
    SELECT * INTO f FROM foods WHERE public_id=(p_payload->>'food_public_id')::uuid AND location_id=p_location FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unknown food.' USING ERRCODE='22023'; END IF;
    IF f.row_version<>(p_payload->>'food_row_version')::bigint THEN
        RAISE EXCEPTION 'Stale food.' USING ERRCODE='55000',DETAIL='stale_object';
    END IF;
    before_version:=f.row_version;
    SELECT * INTO v FROM food_data_proposals WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
    IF v.row_version<>p_target_version OR v.status<>'open' THEN
        RAISE EXCEPTION 'Stale proposal.' USING ERRCODE='55000',DETAIL='stale_object';
    END IF;
    IF v.food_id IS NOT NULL AND v.food_id<>f.id THEN RAISE EXCEPTION 'Different proposal target.' USING ERRCODE='55000'; END IF;
    links:=master_food_links(f.id); merged:=links;
    FOREACH field IN ARRAY fields LOOP
        changed:=false;
        IF field IN ('density_g_per_ml','piece_weight_g') THEN
            value:=(selected->>field)::numeric;
            IF NOT master_factor(value) THEN RAISE EXCEPTION 'Invalid factor.' USING ERRCODE='P1901'; END IF;
            IF (to_jsonb(f)->>field)::numeric IS NULL THEN
                IF field='density_g_per_ml' THEN f.density_g_per_ml:=value; ELSE f.piece_weight_g:=value; END IF;
                changed:=true;
            ELSIF (to_jsonb(f)->>field)::numeric<>value THEN
                RAISE EXCEPTION 'Confirmed factor differs.' USING ERRCODE='55000';
            END IF;
        ELSIF field='category_code' THEN
            category:=(refs->>'category_id')::bigint;
            IF f.category_id IS NULL THEN f.category_id:=category; changed:=true;
            ELSIF f.category_id<>category THEN RAISE EXCEPTION 'Confirmed category differs.' USING ERRCODE='55000'; END IF;
        ELSIF field='labels' THEN
            FOR item IN SELECT x FROM jsonb_array_elements(refs->'labels') x LOOP
                IF NOT merged->'labels' @> jsonb_build_array(item) THEN
                    merged:=jsonb_set(merged,'{labels}',(merged->'labels')||jsonb_build_array(item)); changed:=true;
                END IF;
            END LOOP;
        ELSE
            FOR item IN SELECT x FROM jsonb_array_elements(refs->'allergens') x LOOP
                SELECT x INTO current_item FROM jsonb_array_elements(merged->'allergens') x WHERE x->'id'=item->'id';
                IF FOUND AND current_item->'presence'<>item->'presence' THEN
                    RAISE EXCEPTION 'Confirmed allergen presence differs.' USING ERRCODE='55000';
                ELSIF NOT FOUND THEN
                    merged:=jsonb_set(merged,'{allergens}',(merged->'allergens')||jsonb_build_array(item)); changed:=true;
                END IF;
            END LOOP;
            IF changed THEN f.allergen_review_status:='not_checked'; END IF;
        END IF;
        IF changed THEN adopted:=array_append(adopted,field); ELSE unchanged:=array_append(unchanged,field); END IF;
    END LOOP;
    IF cardinality(adopted)>0 THEN
        PERFORM master_replace_food_links(f.id,p_location,
          (CASE WHEN 'labels'=ANY(adopted) THEN jsonb_build_object('labels',merged->'labels') ELSE '{}'::jsonb END)||
          (CASE WHEN 'allergens'=ANY(adopted) THEN jsonb_build_object('allergens',merged->'allergens') ELSE '{}'::jsonb END));
        UPDATE foods SET density_g_per_ml=f.density_g_per_ml,piece_weight_g=f.piece_weight_g,
          category_id=f.category_id,allergen_review_status=f.allergen_review_status,updated_by=p_actor
          WHERE id=f.id RETURNING row_version INTO f.row_version;
    END IF;
    SELECT COALESCE(array_agg(k ORDER BY k),'{}') INTO unsupported FROM jsonb_object_keys(v.payload) k
      WHERE k NOT IN ('density_g_per_ml','piece_weight_g','category_code','allergens','labels');
    stamp:=clock_timestamp();
    decision:=jsonb_build_object('status','accepted','decided_at',stamp,'adopted',adopted,'unchanged',unchanged,
      'not_supported',unsupported,'food_public_id',f.public_id,'food_row_version_before',before_version,
      'food_row_version_after',f.row_version);
    UPDATE food_data_proposals SET food_id=f.id,status='accepted',decided_by=p_actor,decided_at=stamp,
      decision_detail=decision,updated_by=p_actor WHERE id=v.id;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food_proposal',v.public_id,'accept',
      v.row_version,v.row_version+1,decision||jsonb_build_object('source_reference',v.source_reference));
    RETURN decision;
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range OR check_violation OR not_null_violation THEN
    RAISE EXCEPTION 'Invalid proposal decision.' USING ERRCODE='P1901';
END;
$fn$;
CREATE FUNCTION reject_proposal_v21(p_actor bigint,p_actor_version bigint,p_location bigint,
    p_target uuid,p_target_version bigint,p_payload jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,cafeteria,pg_temp AS $fn$
DECLARE v food_data_proposals%ROWTYPE; decision jsonb; stamp timestamptz; food uuid;
BEGIN
    PERFORM require_master_data_actor(p_actor,p_actor_version,'recipe.import');
    PERFORM master_location(p_location);
    PERFORM master_expectation(p_target,p_target_version);
    PERFORM master_payload(p_payload,ARRAY['reason']);
    PERFORM master_text(p_payload->>'reason',500,false);
    SELECT * INTO v FROM food_data_proposals WHERE public_id=p_target AND location_id=p_location FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Unknown proposal.' USING ERRCODE='22023'; END IF;
    IF v.row_version<>p_target_version OR v.status<>'open' THEN
        RAISE EXCEPTION 'Stale proposal.' USING ERRCODE='55000',DETAIL='stale_object';
    END IF;
    SELECT public_id INTO food FROM foods WHERE id=v.food_id AND location_id=p_location;
    stamp:=clock_timestamp();
    decision:=jsonb_build_object('status','rejected','decided_at',stamp,'adopted','[]'::jsonb,'unchanged','[]'::jsonb,
      'not_supported','[]'::jsonb,'food_public_id',food,'food_row_version_before',NULL,'food_row_version_after',NULL);
    UPDATE food_data_proposals SET status='rejected',decided_by=p_actor,decided_at=stamp,
      decision_detail=decision,updated_by=p_actor WHERE id=v.id;
    PERFORM master_audit(p_actor,p_actor_version,p_location,'food_proposal',v.public_id,'reject',
      v.row_version,v.row_version+1,decision||jsonb_build_object('reason',master_text(p_payload->>'reason',500,false)));
    RETURN decision;
END;
$fn$;

-- Only fixed public verbs are callable by the application.
REVOKE ALL ON FUNCTION
master_text(text,integer,boolean),
master_factor(numeric),
master_quantity(numeric),
master_json_valid(jsonb,integer),
protect_master_data(),
protect_food_proposal(),
require_master_data_actor(bigint,bigint,text),
master_location(bigint),
master_audit(bigint,bigint,bigint,text,uuid,text,bigint,bigint,jsonb),
master_payload(jsonb,text[]),
master_expectation(uuid,bigint),
master_lock_food_refs(jsonb),
master_food_links(bigint),
master_replace_food_links(bigint,bigint,jsonb),
master_food_category_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
master_tag_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
master_storage_location_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
master_unit_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
master_food_mutate(text,bigint,bigint,bigint,uuid,bigint,jsonb),
create_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
rename_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_food_active_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_tags_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_metadata_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_food_allergen_review_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_storage_locations_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
accept_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
reject_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb) FROM PUBLIC,cafeteria_app,cafeteria_backup,cafeteria_auth_issuer;
GRANT EXECUTE ON FUNCTION
create_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_food_category_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_tag_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_storage_location_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
rename_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_active_unit_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
update_food_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_food_active_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_tags_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_metadata_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
set_food_allergen_review_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
replace_food_storage_locations_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
create_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
accept_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb),
reject_proposal_v21(bigint,bigint,bigint,uuid,bigint,jsonb) TO cafeteria_app;
GRANT SELECT ON measurement_units,food_categories,foods,tags,food_tags,food_labels,food_allergens,
 storage_locations,food_storage_locations,food_data_proposals TO cafeteria_app,cafeteria_backup;
GRANT SELECT ON SEQUENCE measurement_units_id_seq,food_categories_id_seq,foods_id_seq,tags_id_seq,
 storage_locations_id_seq,food_data_proposals_id_seq TO cafeteria_backup;
COMMIT;
