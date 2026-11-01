-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.2.3                                      //
-- // Date : 2023-02-17                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V10.2

UPDATE `${prefix}reportparameter`  
SET paramType='milestoneTypeList' where idReport=62 and paramType='milestoneList';
