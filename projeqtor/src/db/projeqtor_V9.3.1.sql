-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.3.1                                       //
-- // Date : 2021-10-01                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V9.3

UPDATE `${prefix}reportparameter` set paramType='projectList' where paramType='ProjectList';
