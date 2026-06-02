-- ============================================================
-- 테스트 데이터 초기화
-- 모든 배치 관련 테이블의 데이터를 삭제한다.
-- FK 제약 조건 순서를 고려하여 역순으로 삭제.
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

TRUNCATE TABLE shap_explanation;
TRUNCATE TABLE s_calculation_request;
TRUNCATE TABLE s_evaluation_history;
TRUNCATE TABLE batch_execution_history;
TRUNCATE TABLE s_input_feature;

SET FOREIGN_KEY_CHECKS = 1;
