-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 9.1.0                                       //
-- // Date : 2020-01-11                                     //
-- ///////////////////////////////////////////////////////////


INSERT INTO `${prefix}menu` (`id`,`name`,`idMenu`,`type`,`sortOrder`,`level`,`idle`,`menuClass`) VALUES
(257, 'menuViewAllSubTask', 7, 'item', 121, Null, 0, 'Work');

INSERT INTO `${prefix}modulemenu` (`idModule`,`idMenu`,`hidden`,`active`) VALUES
(3,257,0,(select `active` from `${prefix}module` where id=3)),
(1,252,0,(select `active` from `${prefix}module` where id=1)),
(1,253,0,(select `active` from `${prefix}module` where id=1)),
(1,90,0,(select `active` from `${prefix}module` where id=1)),
(1,181,0,(select `active` from `${prefix}module` where id=1)),
(10,90,0,(select `active` from `${prefix}module` where id=10)),
(10,181,0,(select `active` from `${prefix}module` where id=10)),
(1,100006001,0,(select `active` from `${prefix}module` where id=1)),
(2,100006001,0,(select `active` from `${prefix}module` where id=2)),
(4,100006001,0,(select `active` from `${prefix}module` where id=4)),
(10,100006001,0,(select `active` from `${prefix}module` where id=10)),
(1,169,0,(select `active` from `${prefix}module` where id=1)),
(10,169,0,(select `active` from `${prefix}module` where id=10));

INSERT INTO `${prefix}navigation` (`id`, `name`, `idParent`, `idMenu`,`sortOrder`,`idReport`) VALUES
(336,'menuViewAllSubTask',3,257,55,0),
(337,'menuViewAllSubTask',5,257,35,0);

INSERT INTO `${prefix}habilitation` (`idProfile`, `idMenu`, `allowAccess`) VALUES
(1,257,1),
(2,257,1),
(3,257,1);

INSERT INTO `${prefix}accessright` (`idProfile`, `idMenu`, `idAccessProfile`) VALUES
(1,257,8),
(2,257,8),
(3,257,8);


INSERT INTO `${prefix}parameter` (`parameterCode`, `parameterValue`) VALUES 
('displaySubTask','YES');

CREATE TABLE `${prefix}subtask` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `refType` varchar(100) DEFAULT NULL,
  `refId` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idProject` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idTargetProductVersion` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `sortOrder` int(5) unsigned DEFAULT NULL COMMENT '5',
  `name` varchar(200) DEFAULT NULL,
  `idPriority` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idResource` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `handled` int(1) unsigned DEFAULT 0  COMMENT '1',
  `done` int(1) unsigned DEFAULT 0  COMMENT '1',
  `idle` int(1) unsigned DEFAULT 0  COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;


CREATE TABLE `${prefix}workcommand` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idCommand` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idWorkUnit` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idComplexity` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `name` varchar(200) DEFAULT NULL,
  `unitAmount` int(12) unsigned DEFAULT NULL COMMENT '12',
  `commandQuantity` int(5) unsigned DEFAULT '0' COMMENT '5',
  `commandAmount` int(12) unsigned DEFAULT NULL COMMENT '12',
  `doneQuantity` int(5) unsigned DEFAULT '0' COMMENT '5',
  `doneAmount` int(12) unsigned DEFAULT NULL COMMENT '12',
  `billedQuantity` int(5) unsigned DEFAULT '0' COMMENT '5',
  `billedAmount` int(12) unsigned DEFAULT NULL COMMENT '12',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}workcommanddone` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idCommand` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idWorkCommand` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `refType` varchar(100) DEFAULT NULL,
  `refId` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `doneQuantity` int(5) unsigned DEFAULT '0' COMMENT '5',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

CREATE TABLE `${prefix}workcommandbilled` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `idCommand` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idWorkCommand` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `idBill` int(12)  unsigned DEFAULT NULL COMMENT '12',
  `billedQuantity` int(5) unsigned DEFAULT '0' COMMENT '5',
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

ALTER TABLE `${prefix}planningelement` ADD `idWorkCommand` INT(12) DEFAULT NULL COMMENT '12';

ALTER TABLE `${prefix}project`
ADD `allowReduction` int(1) unsigned DEFAULT 0 COMMENT '1';

ALTER TABLE `${prefix}status`
ADD `setPausedStatus` int(1) unsigned DEFAULT 0 COMMENT '1';

INSERT INTO `${prefix}status` (`name`, `setDoneStatus`, `setIdleStatus`, `color`, `sortOrder`, `idle`, `setHandledStatus`, `isCopyStatus`, `setCancelledStatus`, `setIntoserviceStatus`, `setSubmittedLeave`, `setAcceptedLeave`, `setRejectedLeave`, `fixPlanning`, `setPausedStatus`) VALUES
('paused', '0', '0', '#BABABA', '350', '0', '0', '0', '0', '0', '0', '0', '0', '1', '1');

INSERT INTO `${prefix}workflowstatus` (idWorkflow,idStatusFrom,idStatusTo,idProfile,allowed) 
SELECT 1, 3, (select max(id) from `${prefix}status` where name='paused'), id, 1 from `${prefix}profile`;

INSERT INTO `${prefix}workflowstatus` (idWorkflow,idStatusFrom,idStatusTo,idProfile,allowed)
SELECT 1, (select max(id) from `${prefix}status` where name='paused'), 3 , id, 1 from `${prefix}profile`;

ALTER TABLE `${prefix}project` ADD COLUMN `paused` int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}activity` ADD COLUMN `paused` int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}planningelement` ADD COLUMN `paused` int(1) unsigned DEFAULT 0 COMMENT '1';
ALTER TABLE `${prefix}planningelementbaseline` ADD COLUMN `paused` int(1) unsigned DEFAULT 0 COMMENT '1';

INSERT INTO `${prefix}linkable` ( `name`, `idle`) VALUES ('Budget', 0);

INSERT INTO `${prefix}modulereport` (`idModule`,`idReport`,`hidden`,`active`) VALUES
(12,102,0,(select `active` from `${prefix}module` where id=12)),
(12,103,0,(select `active` from `${prefix}module` where id=12)),
(12,104,0,(select `active` from `${prefix}module` where id=12)),
(1,105,0,(select `active` from `${prefix}module` where id=1)),
(1,106,0,(select `active` from `${prefix}module` where id=1)),
(1,109,0,(select `active` from `${prefix}module` where id=1)),
(1,111,0,(select `active` from `${prefix}module` where id=1)),
(1,66,0,(select `active` from `${prefix}module` where id=1)),
(10,66,0,(select `active` from `${prefix}module` where id=10)),
(1,67,0,(select `active` from `${prefix}module` where id=1)),
(10,67,0,(select `active` from `${prefix}module` where id=10)),
(1,108,0,(select `active` from `${prefix}module` where id=1));

INSERT INTO `${prefix}habilitationother` (idProfile, scope , rightAccess) 
SELECT id , 'lockedLeftWork','1' from `${prefix}profile`;

-- REPORT attachment.php

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasPdf`) VALUES
(115, 'reportAttachment', 9, 'attachment.php', 950, 1);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES
(115, 'idUser', 'userList', 10, null), 
(115, 'Idle', 'boolean', 20, true);

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 115, 1),
(2, 115, 1),
(3, 115, 1);

INSERT INTO `${prefix}report` (`id`, `name`, `idReportCategory`, `file`, `sortOrder`, `hasExcel`) VALUES
(116, 'reportWorkTwoDate',1, 'work.php', 130,'1'),
(117, 'reportWorkDetailTwoDate',1, 'workDetailed.php', 134,'1'),
(118, 'reportApprovalDocument',4, 'documentApproval.php', 470,'0');

INSERT INTO `${prefix}habilitationreport` (`idProfile`, `idReport`, `allowAccess`) VALUES 
(1, 116, 1),
(1, 117, 1),
(1, 118, 1);

INSERT INTO `${prefix}reportparameter` (`idReport`, `name`, `paramType`, `sortOrder`, `defaultValue`) VALUES 
(116, 'idProject', 'projectList', 10, 'currentProject'),
(116,'idTeam','teamList',15,null),
(116, 'idOrganization', 'organizationList', 20,null),
(116,'startDate','date',25,'today'),
(116,'endDate','date',30,'today'),
(117, 'idProject', 'projectList', 10, 'currentProject'),
(117,'idTeam','teamList',15,null),
(117, 'idOrganization', 'organizationList', 20,null),
(117,'startDate','date',25,'today'),
(117,'endDate','date',30,'today'),
(118, 'idProject', 'projectList', 10, 'currentProject');


INSERT INTO `${prefix}modulereport` (`idModule`,`idReport`,`hidden`,`active`) VALUES
(3,116,0,1),
(3,117,0,1),
(2,118,0,1),
(1,118,0,1);

ALTER TABLE `${prefix}document` ADD COLUMN `idApprovalStatus` int(12) unsigned DEFAULT NULL COMMENT '12';

CREATE TABLE `${prefix}approvalstatus` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT COMMENT '12',
  `name` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=innoDB DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}approvalstatus` (`name`) VALUES
('noApprobationDoc'),
('rejectDoc'),
('waitApprobDoc'),
('approvedDoc');
