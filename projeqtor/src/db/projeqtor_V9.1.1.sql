-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.0.5                                       //
-- // Date : 2021-03-16                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V9.1

ALTER TABLE `${prefix}planningelementbaseline` ADD `idWorkCommand` INT(12) DEFAULT NULL COMMENT '12';

DELETE FROM `${prefix}accessright` WHERE idMenu=257;
