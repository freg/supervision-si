-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 11.1.3                                      //
-- // Date : 2024-01-20                                     //
-- ///////////////////////////////////////////////////////////

ALTER TABLE `${prefix}reportlayout` CHANGE `idFilterCriteria` `idFilter` INT UNSIGNED NULL DEFAULT NULL COMMENT '12';
