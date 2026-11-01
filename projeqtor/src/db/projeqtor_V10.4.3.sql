-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.4.3                                      //
-- // Date : 2023-07-19                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V10.4

UPDATE `${prefix}reportparameter` set sortOrder=40 where idReport=106 and name='year';
UPDATE `${prefix}reportparameter` set paramType='projectList' where paramType='ProjectList' and name='idProject';

INSERT INTO `${prefix}modulemenu` (idModule, idMenu, hidden, active) VALUES
(6, 287, 0, 1),
(6, 288, 1, 1);

-- #7264
DELETE from `${prefix}tempupdate`;
INSERT INTO `${prefix}tempupdate` (idOther, workValue) SELECT idMenu, active FROM `${prefix}modulemenu` WHERE idMenu in (75,80);
UPDATE `${prefix}modulemenu` SET active=(select workValue from `${prefix}tempupdate` where idOther=75) WHERE idMenu=287;
UPDATE `${prefix}modulemenu` SET active=(select workValue from `${prefix}tempupdate` where idOther=80) WHERE idMenu=288;
DELETE from `${prefix}tempupdate`;

-- #7265
INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
  (2,287,1),
  (2,288,1);
UPDATE `${prefix}habilitation` SET allowAccess=0 WHERE idProfile=3 and idMenu=288;
UPDATE `${prefix}accessright` SET idAccessProfile=1000001 WHERE idProfile=1 and idMenu=288;
UPDATE `${prefix}accessright` SET idAccessProfile=1000002 WHERE idProfile=3 and idMenu=288;