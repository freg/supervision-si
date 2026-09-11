-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 11.0.0                                       //
-- // Date : 2023-06-26                                    //
-- ///////////////////////////////////////////////////////////

ALTER TABLE `${prefix}plugin` ADD licenceKey varchar(400) DEFAULT NULL;

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`,`idle`,`hasPrint`, `hasPdf`, `hasToday`, `hasWord`, `hasExcel`) VALUES
(141, 'reportCostMonthlyPerActivity', 6, 'globalCostPlanningPerActivity.php', 625,0, 1, 1, 1, 0, 1);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES 
(141, 'idProject', 'projectList', 10, 'currentProject'),
(141,'idOrganization','organizationList',20,null),
(141, 'idTeam', 'teamList', 30, null),
(141, 'month', 'month', 50, 'currentYear');

INSERT INTO `${prefix}habilitationreport` (`idReport`, `idProfile`,  `allowAccess`) VALUES
(141, 1, 1),
(141, 2, 1),
(141, 3, 1);

ALTER TABLE `${prefix}project` 
ADD COLUMN `idCalendarDefinition` int(12) unsigned DEFAULT NULL COMMENT '12';

INSERT INTO `${prefix}today` (`idUser`,`scope`,`staticSection`,`idReport`,`sortOrder`,`idle`)
SELECT id, 'newGui','Projects',null,1,0 FROM `${prefix}resource` where isUser=1 and idle=0;
INSERT INTO `${prefix}today` (`idUser`,`scope`,`staticSection`,`idReport`,`sortOrder`,`idle`)
SELECT id, 'newGui','Message',null,2,0 FROM `${prefix}resource` where isUser=1 and idle=0;
INSERT INTO `${prefix}today` (`idUser`,`scope`,`staticSection`,`idReport`,`sortOrder`,`idle`)
SELECT id, 'newGui','Documents',null,3,0 FROM `${prefix}resource` where isUser=1 and idle=0;
INSERT INTO `${prefix}today` (`idUser`,`scope`,`staticSection`,`idReport`,`sortOrder`,`idle`)
SELECT id, 'newGui','Todo',null,4,0 FROM `${prefix}resource` where isUser=1 and idle=0;
INSERT INTO `${prefix}today` (`idUser`,`scope`,`staticSection`,`idReport`,`sortOrder`,`idle`)
SELECT id, 'newGui','ResponsibleTodoList',null,5,0 FROM `${prefix}resource` where isUser=1 and idle=0;
INSERT INTO `${prefix}today` (`idUser`,`scope`,`staticSection`,`idReport`,`sortOrder`,`idle`)
SELECT id, 'newGui','News',null,6,0 FROM `${prefix}resource` where isUser=1 and idle=0;

INSERT INTO `${prefix}menu` (`id`, `name`, `idMenu`, `type`, `sortOrder`, `level`, `idle`, `menuClass`) VALUES 
(289, 'menuStartGuide', 0, 'item', 1,  null, 0, 'Work Risk RequirementTest Financial Review');
INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES 
(1,289,1);