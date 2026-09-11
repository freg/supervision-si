-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 12.2.0                                      //
-- // Date : 2025-04-20                                     //
-- ///////////////////////////////////////////////////////////

ALTER TABLE `${prefix}filtercriteria` ADD `isGroup` INT(1) unsigned DEFAULT '0' COMMENT '1';
ALTER TABLE `${prefix}filtercriteria` ADD `indentLevel` INT(1) unsigned DEFAULT '0' COMMENT '1';

-- #6772
INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('ResourceTeam', 0); 
INSERT INTO `${prefix}importable` (`name`, `idle`) VALUES ('ResourceTeamAffectation', 0);

-- #10076
DELETE FROM `${prefix}notifiable` WHERE notifiableItem in ('InputMailbox','Status','Workflow','LeaveType');
INSERT INTO `${prefix}notifiable` (notifiableitem, name, idle) VALUES 
('ActivityExpense', 'ActivityExpense',0),
('IndividualExpense', 'IndividualExpense',0),
('ActivityPlanningElement', 'ActivityPlanningElement',0),
('ProjectPlanningElement', 'ProjectPlanningElement',0),
('MilestonePlanningElement', 'MilestonePlanningElement',0);

CREATE TABLE `${prefix}paymentdatemode` (
  `id` int(12) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(100),
  `sortOrder` int(3) unsigned DEFAULT NULL COMMENT '3',
  `idle` int(1) unsigned DEFAULT '0' COMMENT '1',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB  DEFAULT CHARSET=utf8mb4 COLLATE utf8mb4_general_ci ;

INSERT INTO `${prefix}paymentdatemode` (`id`, `name`, `sortOrder`, `idle`) VALUES
(1, 'paymentStartDateMode', 100, 0),
(2, 'paymentMedianDateMode', 200, 0),
(3, 'paymentEndDateMode', 300, 0);

ALTER TABLE `${prefix}expense` ADD `idPaymentDateMode` int(12) unsigned DEFAULT NULL COMMENT '12';
CREATE INDEX `expenseActivity` ON `${prefix}expense` (`idActivity`);

-- Default duration
ALTER TABLE `${prefix}type` ADD `defaultDuration` INT(5) unsigned DEFAULT null COMMENT '5';
-- UPDATE `${prefix}type` SET `defaultDuration`=1 WHERE idPlanningMode IN (8,14,27,28,29,30);
ALTER TABLE `${prefix}planningmode` ADD `defaultDuration` INT(5) unsigned DEFAULT null COMMENT '5';
UPDATE `${prefix}planningmode` SET `defaultDuration`=1 WHERE code IN ('FDUR', 'DDUR', 'CDUR');

-- #7549
ALTER TABLE `${prefix}resource` ADD `mustChangePassword` int(1) unsigned DEFAULT 0 COMMENT '1';