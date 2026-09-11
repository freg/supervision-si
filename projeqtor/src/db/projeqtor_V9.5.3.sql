-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.5.1                                       //
-- // Date : 2022-03-30                                     //
-- ///////////////////////////////////////////////////////////

DELETE FROM `${prefix}parameter`  WHERE parameterCode='kanbanIdKanban' and parameterValue like '<div%';